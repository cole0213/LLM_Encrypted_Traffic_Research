"""
e1_from_csv.py — E1 재검증(파일럿). parse_pcap 산출 CSV(gem_feats.csv 등)를 직접 읽어
                 패킷 피처만으로 추론 조건을 분류한다. (pcap 재추출 없이 정본 CSV로 재현)

목적: e1_classify.py와 동일한 규칙(질문별 GroupKFold, 패킷피처만)에 length-only·ttfa-only 대조를
      더해 이미 추출된 CSV에 대해 재실행, 이진/3클래스 정확도를 재확인한다.
      대조군: length-only(answer_tokens — 추론토큰을 포함하는 provider 는 자동 보정) /
              ttfa-only(pkt_gap_ms 첫침묵) / timing-only(크기 계열 제외) / packet(8피처 전부).
      pcap↔log 매칭이 애매할 때 정본 feats CSV로 숫자를 검증하는 용도.
입력: feats CSV 경로(들). 컬럼 = condition,q_idx,pkt_gap_ms,up_bytes,down_bytes,up_pkts,
      down_pkts,down_iat_mean_ms,down_pkt_mean,down_pkt_max,output_tokens ...
출력: 콘솔(정확도·혼동행렬·피처중요도).
사용: python3 e1_from_csv.py out/gem_feats.csv
작성일: 2026-09-23
"""
import sys
import csv
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

# e1_classify.py와 동일한 8개 패킷 피처(길이=output_tokens 제외).
PKT_FEATS = ["pkt_gap_ms", "up_bytes", "down_bytes", "up_pkts", "down_pkts",
             "down_iat_mean_ms", "down_pkt_mean", "down_pkt_max"]

# 업링크(요청) 피처는 설정값을 그대로 누출한다.
#   gem_strict 에서 up_bytes 중앙값 = no_think 808 / think_low 875 / think_high 876.
#   no_think 만 thinking_config 필드를 안 보내 요청이 ~67바이트 짧고, low/high 는 글자 1개 차이뿐.
#   즉 분류기가 '추론이 일어났나'가 아니라 '요청에 설정 필드가 붙었나'를 읽을 수 있다(라벨 누수).
# → 하향(응답)만 쓴 결과를 함께 내서 누수 없이도 성립하는지 확인한다.
DOWN_FEATS = [f for f in PKT_FEATS if not f.startswith("up_")]

# 크기 계열 피처는 provider 에 따라 '추론의 사이드채널'이 아닐 수 있다.
#   * Groq : 답을 한 글자로 고정했는데도 down_bytes AUC 가 0.85~0.91 나왔다. 원인은
#            응답 끝 usage 객체의 토큰 수 '숫자 자릿수'(33 → 227 → 1204)가 평문 길이를
#            늘린 것. 자릿수를 고정하면 추론량 하위25% vs 상위25% 의 down_bytes 가
#            완전히 같아진다(차이 0). 즉 추론 흔적이 아니라 라벨의 그림자다.
#   * Gemini: 자릿수를 고정해도 추론토큰당 약 3.9바이트로 선형 증가(3자리 구간 AUC 1.000).
#            이쪽은 진짜 데이터가 더 내려온 것이라, 추론 요약 전송이 의심된다.
# 어느 쪽이든 '암호화된 트래픽의 미세 신호'라는 주장과는 성격이 다르므로,
# 크기를 전혀 안 쓴 타이밍 전용 수치를 항상 같이 낸다. 이게 방어 가능한 하한선이다.
TIME_FEATS = ["pkt_gap_ms", "down_iat_mean_ms"]

# --reasoned-only 플래그(main 에서 설정). 자세한 이유는 run() 안 주석 참조.
REASONED_ONLY = False


def load(path):
    """feats CSV → 행 리스트(숫자 변환, 빈칸/None 은 NaN·0 처리)."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rec = {"condition": r["condition"], "q_idx": int(r["q_idx"])}
            for k in PKT_FEATS:
                v = r.get(k, "")
                rec[k] = float(v) if v not in ("", "None", None) else np.nan
            ot = r.get("output_tokens", "")
            rec["output_tokens"] = float(ot) if ot not in ("", "None", None) else 0.0
            # length-only 대조에 쓸 '답 길이'. parse_pcap 이 넣어준 answer_tokens 가 정답이고,
            # 그 열이 없는 옛 CSV 는 output_tokens 로 떨어진다(아래 _length_src 가 검사·경고).
            an = r.get("answer_tokens", "")
            rec["answer_tokens"] = float(an) if an not in ("", "None", None) else None
            th = r.get("thoughts_tokens", "")
            rec["thoughts_tokens"] = float(th) if th not in ("", "None", None) else None
            # 길이 통제가 깨진 콜을 걸러내기 위한 정보.
            #   (a) 토큰 한계까지 가서 답을 못 낸 콜 — Groq q4 think_high 5/5 등. app_ttft 가 빈다.
            #   (b) 지시를 무시하고 문장으로 답한 콜 — Gemini 3차 q4 think_high 1건(answer_chars=224).
            #       이쪽은 app_ttft 가 있어서 (a) 필터에 안 걸린다.
            # 둘 다 '출력 길이 고정'이라는 전제를 깬 콜이므로 분석에서 뺀다.
            at = r.get("app_ttft_ms", "")
            ac = r.get("answer_chars", "")
            tr = r.get("truncated", "")
            rec["answered"] = at not in ("", "None", None)
            rec["answer_chars"] = float(ac) if ac not in ("", "None", None) else None
            rec["truncated"] = (str(tr) == "1")
            rows.append(rec)
    return rows


def cv_eval(X, y, groups, model, n_splits):
    """질문별 GroupKFold → 전체 예측 모아 정확도 + 정답/예측 반환."""
    gkf = GroupKFold(n_splits=n_splits)
    yt, yp = [], []
    for tr, te in gkf.split(X, y, groups):
        model.fit(X[tr], y[tr])
        yt.extend(y[te]); yp.extend(model.predict(X[te]))
    return accuracy_score(yt, yp), np.array(yt), np.array(yp)


def _length_src(sub):
    """length-only 대조에 쓸 '답 길이' 벡터와, 그 값을 믿어도 되는지 알려주는 메모.

    answer_tokens 열이 있으면 그대로 쓴다. 없는 옛 CSV 는 output_tokens 로 떨어지는데,
    그 값이 추론 토큰을 포함하는 provider 면 length-only 가 사실상 정답 라벨을 보는 것이라
    "길이를 통제했다"는 주장과 모순된다. 그래서 (output - thoughts) 가 상수인지 검사해
    해당하면 그 차이를 답 길이로 복원하고, 무엇을 썼는지 출력에 적는다.
    """
    if any(r.get("answer_tokens") is not None for r in sub):
        return [r.get("answer_tokens") or 0.0 for r in sub], "answer_tokens"
    diffs = {r["output_tokens"] - (r["thoughts_tokens"] or 0.0)
             for r in sub if r.get("thoughts_tokens") is not None}
    if len(diffs) == 1 and diffs != {0.0}:
        d = diffs.pop()
        return ([d] * len(sub),
                f"output-thoughts={d:g} 고정 → 복원(원본 output_tokens 는 추론 포함이라 무효)")
    return [r["output_tokens"] for r in sub], "output_tokens"


def run(rows, labels, title):
    # 지정 조건만, pkt_gap 결측 제거, 출력 길이 고정이 깨진 콜 제거.
    cand = [r for r in rows if r["condition"] in labels and not np.isnan(r["pkt_gap_ms"])]
    # 답 글자수의 최빈값을 '정상'으로 보고 거기서 벗어난 콜을 뺀다.
    #   (CSV 에 answer_chars 가 없는 옛 파일은 이 검사를 건너뛰고 app_ttft 유무만 본다.)
    acs = [r["answer_chars"] for r in cand if r.get("answer_chars") is not None]
    modal = max(set(acs), key=acs.count) if acs else None
    def ok(r):
        if not r.get("answered", True) or r.get("truncated"):
            return False
        if modal is not None and r.get("answer_chars") is not None:
            return r["answer_chars"] == modal
        return True
    sub = [r for r in cand if ok(r)]
    dropped = len(cand) - len(sub)
    # --reasoned-only: 추론이 실제로 일어난 콜만 남긴다.
    #   Gemini 는 think_low 의 83%(3차 75/90)가 추론 토큰 0이라, 분류기가 '얼마나 깊이
    #   생각했나'가 아니라 '생각을 했나 안 했나'를 맞히고 있을 수 있다. 이 옵션으로
    #   추론>0 끼리만 비교하면 그 두 가지가 분리된다(3차 Gemini low vs high 는
    #   AUC 기준 0.943 → 0.726 으로 떨어졌다. 단 n_low=15 라 신뢰구간이 넓다).
    reasoned_dropped = 0
    if REASONED_ONLY:
        before = len(sub)
        sub = [r for r in sub if (r.get("thoughts_tokens") or 0) > 0]
        reasoned_dropped = before - len(sub)
    if not sub:
        print(f"\n[{title}] 해당 조건 데이터 없음 (labels={labels})"); return
    y = np.array([r["condition"] for r in sub])
    groups = np.array([r["q_idx"] for r in sub])
    n_q = len(set(groups))
    Xpkt = np.array([[r[f] for f in PKT_FEATS] for r in sub], dtype=float)
    Xpkt = np.nan_to_num(Xpkt)                    # 남은 NaN → 0
    len_vals, len_src = _length_src(sub)
    Xlen = np.array([[v] for v in len_vals], dtype=float)
    # TTFA-only = 요청→첫응답 침묵(pkt_gap_ms) 단일 피처. "그냥 첫 침묵만으로 되냐 vs 시퀀스 전체 필요하냐" 대조.
    Xttfa = np.nan_to_num(np.array([[r["pkt_gap_ms"]] for r in sub], dtype=float))
    print(f"\n{'='*58}\n[{title}] n={len(sub)}, 질문 {n_q}개 (leave-one-question-out)")
    print(f"  클래스 분포: { {c: int((y==c).sum()) for c in labels} }")
    if reasoned_dropped:
        print(f"  ※ --reasoned-only: 추론 토큰 0/미보고 {reasoned_dropped}건 추가 제외")
    if dropped:
        print(f"  ※ 출력 길이 고정이 깨진 콜 {dropped}건 제외(토큰 한계 도달 또는 지시 무시)")
        # 질문별 교차검증이라, 어떤 질문의 한 조건이 통째로 비면 그 회차가 성립하지 않는다.
        from collections import Counter
        per = Counter((r["q_idx"], r["condition"]) for r in sub)
        empty = [(q, c) for q in sorted(set(groups)) for c in labels if per[(q, c)] == 0]
        if empty:
            print(f"  ※ 경고: 아래 (질문, 조건)은 남은 표본이 0 — 해당 회차 평가가 불완전함")
            for q, c in empty:
                print(f"       q{q} {c}")

    a_maj, *_ = cv_eval(Xpkt, y, groups, DummyClassifier(strategy="most_frequent"), n_q)
    a_len, *_ = cv_eval(Xlen, y, groups, RandomForestClassifier(n_estimators=300, random_state=42), n_q)
    a_ttfa, *_ = cv_eval(Xttfa, y, groups, RandomForestClassifier(n_estimators=300, random_state=42), n_q)
    a_pkt, yt, yp = cv_eval(Xpkt, y, groups, RandomForestClassifier(n_estimators=300, random_state=42), n_q)
    # 업링크 제외판: 요청 크기로 설정값을 읽는 경로를 막고도 되는지 확인(위 DOWN_FEATS 주석 참조).
    Xdown = np.nan_to_num(np.array([[r[f] for f in DOWN_FEATS] for r in sub], dtype=float))
    a_down, ytd, ypd = cv_eval(Xdown, y, groups, RandomForestClassifier(n_estimators=300, random_state=42), n_q)
    # 타이밍 전용: 크기 계열을 전부 빼고 pkt_gap + down_iat 만. (TIME_FEATS 주석 참조)
    Xtime = np.nan_to_num(np.array([[r[f] for f in TIME_FEATS] for r in sub], dtype=float))
    a_time, *_ = cv_eval(Xtime, y, groups, RandomForestClassifier(n_estimators=300, random_state=42), n_q)
    print(f"  majority(찍기)      : {a_maj:.3f}")
    print(f"  length-only(길이만) : {a_len:.3f}   ← 이걸 이겨야 함  [출처: {len_src}]")
    print(f"  ttfa-only(첫침묵만) : {a_ttfa:.3f}   ← pkt_gap_ms 하나")
    print(f"  timing-only(타이밍만): {a_time:.3f}   ← 크기 계열 전부 제외, 가장 보수적인 값")
    print(f"  packet model(전체)  : {a_pkt:.3f}   ← 업링크 포함(요청 크기로 설정값 누출 가능)")
    print(f"  packet model(하향만): {a_down:.3f}   ← 업링크 제외, 누수 없는 정직한 값")
    print("  하향 혼동행렬 (행=정답, 열=예측):")
    for lab, row in zip(labels, confusion_matrix(ytd, ypd, labels=list(labels))):
        print(f"    {lab:11s} {row}")
    pd_ = RandomForestClassifier(n_estimators=300, random_state=42).fit(Xdown, y)
    imp_d = sorted(zip(DOWN_FEATS, pd_.feature_importances_), key=lambda z: -z[1])
    print("  하향 피처 중요도:", ", ".join(f"{f}={w:.2f}" for f, w in imp_d[:5]))
    print(f"  혼동행렬 (행=정답, 열=예측) {list(labels)}:")
    for lab, row in zip(labels, confusion_matrix(yt, yp, labels=list(labels))):
        print(f"    {lab:11s} {row}")
    pk = RandomForestClassifier(n_estimators=300, random_state=42).fit(Xpkt, y)
    imp = sorted(zip(PKT_FEATS, pk.feature_importances_), key=lambda z: -z[1])
    print("  피처 중요도:", ", ".join(f"{f}={w:.2f}" for f, w in imp[:5]))


def main():
    global REASONED_ONLY
    args = sys.argv[1:]
    # --reasoned-only : 추론 토큰이 0/미보고인 콜을 빼고 '추론이 일어난 것끼리만' 비교.
    if "--reasoned-only" in args:
        REASONED_ONLY = True
        args.remove("--reasoned-only")
    # --pair A,B : 기본 조합 대신 지정한 두 조건만 비교(provider 간 공정 비교용).
    #   Gemini 는 no_think 가 있어 기본이 no vs high 이지만, no_think 가 없는 Groq(gpt-oss)와
    #   맞추려면 양쪽 다 low vs high 로 봐야 비교가 성립한다.
    #   예) python3 e1_from_csv.py out/gem_strict.csv --pair think_low,think_high
    pair = None
    if "--pair" in args:
        k = args.index("--pair")
        pair = [c.strip() for c in args[k + 1].split(",")]
        del args[k:k + 2]
    paths = args or ["out/gem_feats.csv"]
    if pair:
        for p in paths:
            rows = load(p)
            print(f"\n########## {p}  (n={len(rows)}) ##########")
            run(rows, pair, f"지정 비교: {pair[0]} vs {pair[1]}")
        return
    for p in paths:
        rows = load(p)
        print(f"\n########## {p}  (n={len(rows)}) ##########")
        conds = set(r["condition"] for r in rows)
        # 존재하는 얕은 조건(no_think 우선, 없으면 think_low) vs think_high 이진
        shallow = "no_think" if "no_think" in conds else ("think_low" if "think_low" in conds else None)
        if shallow and "think_high" in conds:
            run(rows, [shallow, "think_high"], f"이진: {shallow} vs think_high")
        # 3클래스: Gemini(no/low/high) 우선, 없으면 Groq gpt-oss(low/med/high). 먼저 맞는 것 하나.
        for triple in (["no_think", "think_low", "think_high"],
                       ["think_low", "think_med", "think_high"]):
            if all(c in conds for c in triple):
                nice = {"no_think": "no", "think_low": "low", "think_med": "med", "think_high": "high"}
                short = "/".join(nice.get(t, t) for t in triple)
                run(rows, triple, f"3클래스: {short}")
                break


if __name__ == "__main__":
    main()
