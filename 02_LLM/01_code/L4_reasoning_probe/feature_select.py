"""
feature_select.py — 피처 약 130개에서 최적 조합과 적정 개수를 찾는다(과적합·낙관편향 방지 포함).

왜 필요한가:
  parse_pcap_rich.py 로 피처가 약 130개가 됐는데 표본은 100~180개다.
  피처 수가 표본에 육박하면 분류기가 잡음을 외워 점수가 부풀려진다.
  그래서 '전부 넣은 값'은 상한으로만 보고, 과적합을 막은 선택 결과를 따로 봐야 한다.

두 가지 편향을 각각 막는다 (이 구분이 핵심):

  (1) 선택 누수 — 전체 데이터로 피처를 고른 뒤 교차검증하면 평가할 질문을 이미 보고 고른 셈이다.
      막는 법: 질문별 leave-one-question-out 의 회차마다, 그 회차의 학습 질문들로만 중요도를 구해
      상위 k개를 고르고, 그 k개로 다시 학습해 한 번도 안 본 질문을 예측한다.
      → 아래 (C) '정직한 수치'가 이 방식이다.

  (2) 낙관 편향 — 조합을 수백 개 시도한 뒤 가장 좋은 것만 보고하면, 그 최댓값은 실력이 아니라
      운 좋은 잡음을 고른 것이다. 시도 횟수가 많을수록 최댓값은 더 부풀려진다.
      막는 법: 탐색 결과는 최댓값이 아니라 분포(중앙값·사분위)로 보고하고, 최댓값에는 경고를 단다.
      → 아래 (D) '조합 탐색'이 이 방식이며, 보고용 수치가 아니라 어떤 피처가 자주 들어가는지를 보는 용도다.

무작위성 대응:
  RandomForest 는 시드에 따라 결과가 흔들린다. 모든 설정을 --repeats 회 반복해
  평균과 표준편차를 함께 낸다. 표준편차가 크면 그 수치는 믿을 게 못 된다.

출력:
  (A) 전부 넣기 — 상한. 학습 정확도와의 격차로 과적합을 진단
  (B) 상관 0.95 중복 제거
  (C) 피처 개수 k 별 정직한 수치 (평균 ± 표준편차) — 보고용
  (D) 무작위 조합 탐색 — 분포와 자주 등장한 피처
  (E) 피처 묶음별 (크기 / 타이밍 / 순서열 / 파생) — 어느 계열이 신호를 싣는가
  (F) 회차에서 자주 선택된 피처 순위

사용:
  python3 feature_select.py gemini=out/gem_rich.csv groq=out/groq_rich.csv
  옵션: --pair think_low,think_high  --repeats 5  --random 200  --no-uplink
작성일: 2026-10-05
"""
import sys
import csv
import random
from collections import Counter

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score

# 라벨이거나 식별자여서 피처로 쓰면 안 되는 열.
#   app_ttft_ms / thoughts_tokens / output_tokens 는 API 가 알려준 값이라 관측자는 볼 수 없다.
DROP = {"idx", "q_idx", "condition", "rep",
        "app_ttft_ms", "thoughts_tokens", "output_tokens",
        "answer_chars", "truncated"}
KS = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50]
N_TREES = 200


def load(path, pair, no_uplink):
    rows, feats = [], None
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("condition") not in pair:
                continue
            if r.get("app_ttft_ms") in ("", "None", None):   # 답 못 낸 콜 제외
                continue
            if feats is None:
                feats = [c for c in r if c not in DROP]
                if no_uplink:
                    feats = [c for c in feats if not c.startswith(("up_", "upsz", "upiat"))]
            rows.append({
                "X": [float(r[c]) if r.get(c) not in ("", "None", None) else 0.0 for c in feats],
                "y": r["condition"], "q": int(float(r["q_idx"]))})
    return rows, feats


def mat(rows):
    return (np.nan_to_num(np.array([r["X"] for r in rows], float)),
            np.array([r["y"] for r in rows]),
            np.array([r["q"] for r in rows]))


def rf(seed):
    return RandomForestClassifier(n_estimators=N_TREES, random_state=seed, n_jobs=-1)


def cv_fixed(X, y, g, cols, seed):
    """피처를 고정해 질문별 교차검증. (D)(E) 처럼 조합이 이미 정해진 경우에 쓴다."""
    if not len(cols):
        return 0.5
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=len(set(g))).split(X, y, g):
        m = rf(seed).fit(X[tr][:, cols], y[tr])
        yt.extend(y[te]); yp.extend(m.predict(X[te][:, cols]))
    return accuracy_score(yt, yp)


def cv_all(X, y, g, seed):
    """전체 피처. 학습 정확도도 같이 내서 과적합 폭을 본다."""
    yt, yp, tr_acc = [], [], []
    for tr, te in GroupKFold(n_splits=len(set(g))).split(X, y, g):
        m = rf(seed).fit(X[tr], y[tr])
        tr_acc.append(accuracy_score(y[tr], m.predict(X[tr])))
        yt.extend(y[te]); yp.extend(m.predict(X[te]))
    return accuracy_score(yt, yp), float(np.mean(tr_acc))


def cv_nested_topk(X, y, g, k, feats, seed):
    """정직한 수치 — 선택을 학습 폴드 안에서만 수행한다(선택 누수 차단)."""
    yt, yp, chosen = [], [], Counter()
    for tr, te in GroupKFold(n_splits=len(set(g))).split(X, y, g):
        sel = rf(seed).fit(X[tr], y[tr])                  # 중요도는 학습 폴드로만
        idx = np.argsort(sel.feature_importances_)[::-1][:k]
        chosen.update(feats[i] for i in idx)
        m = rf(seed).fit(X[tr][:, idx], y[tr])
        yt.extend(y[te]); yp.extend(m.predict(X[te][:, idx]))
    return accuracy_score(yt, yp), chosen


def drop_correlated(X, feats, thr=0.95):
    """상관이 매우 높은 피처는 같은 정보를 반복하므로 하나만 남긴다."""
    keep = []
    with np.errstate(invalid="ignore", divide="ignore"):
        C = np.nan_to_num(np.corrcoef(X.T))
    for i in range(X.shape[1]):
        if all(abs(C[i, j]) < thr for j in keep):
            keep.append(i)
    return keep


def family_of(name):
    """피처 이름으로 계열을 가른다. 어느 계열이 신호를 싣는지 보기 위함."""
    if name.startswith(("h",)) and ("_size" in name or "_dt" in name):
        return "순서열"
    if "iat" in name or name in ("pkt_gap_ms", "total_ms", "gap_over_total",
                                 "maxiat_over_mean", "n_stalls", "stall_total_ms", "stall_ratio"):
        return "타이밍"
    if "sz" in name or "bytes" in name or "pkt_mean" in name or "pkt_max" in name:
        return "크기"
    if name.startswith("bin"):
        return "구간"
    return "기타"


def ms(vals):
    """평균 ± 표준편차 문자열."""
    return f"{np.mean(vals):.3f} ± {np.std(vals):.3f}"


def main():
    args = sys.argv[1:]
    pair = ["think_low", "think_high"]
    repeats, n_random = 5, 200
    for flag, conv in (("--pair", None), ("--repeats", int), ("--random", int)):
        if flag in args:
            i = args.index(flag)
            val = args[i + 1]
            if flag == "--pair":
                pair = [c.strip() for c in val.split(",")]
            elif flag == "--repeats":
                repeats = conv(val)
            else:
                n_random = conv(val)
            del args[i:i + 2]
    no_uplink = "--no-uplink" in args
    if no_uplink:
        args.remove("--no-uplink")
    if not args:
        print("사용: python3 feature_select.py gemini=out/gem_rich.csv groq=out/groq_rich.csv")
        return

    for item in args:
        label, _, path = item.partition("=")
        rows, feats = load(path, pair, no_uplink)
        if not rows:
            print(f"[skip] {path} 에 {pair} 데이터 없음"); continue
        X, y, g = mat(rows)
        n_q, nf = len(set(g)), len(feats)
        seeds = [42 + i * 101 for i in range(repeats)]

        print(f"\n{'='*70}")
        print(f"{label or path}   n={len(rows)}  피처 {nf}개  질문 {n_q}개  {pair[0]} vs {pair[1]}")
        print(f"반복 {repeats}회 (시드 변경) · 무작위 조합 {n_random}개")
        print(f"{'='*70}")
        print(f"찍기 기준 {max(Counter(y).values())/len(y):.3f}")

        # (A) 전부 넣기
        a_te, a_tr = zip(*[cv_all(X, y, g, s) for s in seeds])
        print(f"\n(A) 전부 넣기   평가 {ms(a_te)}   학습 {ms(a_tr)}   "
              f"격차 {np.mean(a_tr)-np.mean(a_te):+.3f}")
        print(f"    ※ 격차가 크면 과적합. 피처 {nf}개 vs 표본 {len(rows)}개")

        # (B) 상관 중복 제거
        keep = drop_correlated(X, feats)
        b = [cv_fixed(X, y, g, keep, s) for s in seeds]
        print(f"(B) 상관 0.95 제거   평가 {ms(b)}   남은 피처 {len(keep)}개 "
              f"(중복 {nf-len(keep)}개 제거)")

        # (C) 정직한 수치 — 선택을 학습 폴드 안에서만
        print(f"\n(C) 피처 개수별 — 선택을 학습 폴드 안에서만 (보고용 수치)")
        print(f"    {'k':>4s}  {'평가 (평균 ± 표준편차)':>24s}")
        best_k, best_mean, curves = None, -1, {}
        for k in KS:
            if k > nf:
                break
            accs, chosen_all = [], Counter()
            for s in seeds:
                acc, ch = cv_nested_topk(X, y, g, k, feats, s)
                accs.append(acc); chosen_all.update(ch)
            curves[k] = (accs, chosen_all)
            mark = ""
            if np.mean(accs) > best_mean:
                best_mean, best_k = np.mean(accs), k; mark = "  <- 최고"
            print(f"    {k:>4d}  {ms(accs):>24s}{mark}")
        print(f"\n    최적 k = {best_k}   {ms(curves[best_k][0])}")
        print(f"    ※ 표준편차가 평균 차이보다 크면 k 선택은 의미 없다(잡음 범위).")

        # (D) 무작위 조합 탐색 — 보고용 아님
        print(f"\n(D) 무작위 조합 탐색 (k={best_k}, {n_random}개 조합 x 시드 1개)")
        rnd = random.Random(7)
        results, seen = [], Counter()
        for _ in range(n_random):
            cols = rnd.sample(range(nf), min(best_k, nf))
            acc = cv_fixed(X, y, g, cols, seeds[0])
            results.append((acc, cols))
        accs_only = sorted(a for a, _ in results)
        q1, med, q3 = (accs_only[len(accs_only)//4], accs_only[len(accs_only)//2],
                       accs_only[3*len(accs_only)//4])
        print(f"    분포  최소 {accs_only[0]:.3f} | 1사분위 {q1:.3f} | 중앙 {med:.3f} | "
              f"3사분위 {q3:.3f} | 최대 {accs_only[-1]:.3f}")
        print(f"    ※ 최대값은 {n_random}개 중 운 좋은 하나이므로 낙관 편향이다. 보고하지 말 것.")
        top = sorted(results, key=lambda t: -t[0])[:max(5, n_random // 20)]
        for _, cols in top:
            seen.update(feats[i] for i in cols)
        print(f"    상위 {len(top)}개 조합에 자주 들어간 피처:")
        for f_, c in seen.most_common(10):
            print(f"      {f_:26s} {c:>3d}/{len(top)}  [{family_of(f_)}]")

        # (E) 피처 묶음별
        print(f"\n(E) 피처 묶음별 (그 계열만 썼을 때)")
        fams = {}
        for i, f_ in enumerate(feats):
            fams.setdefault(family_of(f_), []).append(i)
        for fam, cols in sorted(fams.items(), key=lambda t: -len(t[1])):
            accs = [cv_fixed(X, y, g, cols, s) for s in seeds]
            print(f"    {fam:8s} ({len(cols):>3d}개)   {ms(accs)}")

        # (F) 자주 선택된 피처
        print(f"\n(F) k={best_k} 에서 자주 선택된 피처 (총 {n_q*repeats}회 중)")
        for f_, c in curves[best_k][1].most_common(15):
            print(f"    {f_:26s} {c:>3d}/{n_q*repeats}  [{family_of(f_)}]")

    print("\n해석:")
    print("  (A) 학습-평가 격차가 크면 피처가 표본에 비해 많다는 뜻이다.")
    print("  (C) k를 늘려도 평균이 안 오르거나 표준편차 안에서 움직이면 그 이상은 잡음이다.")
    print("  (D) 최대값은 쓰지 말고, 자주 등장한 피처만 참고한다.")
    print("  (E)(F) 가 provider 마다 다르면 '신호를 싣는 경로가 다르다'는 직접 증거다.")


if __name__ == "__main__":
    main()
