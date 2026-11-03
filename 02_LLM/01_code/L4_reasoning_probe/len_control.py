"""
len_control.py — 답 길이를 통제해도 추론 신호가 남는가.

목적: 3-16(thoughtSignature 누출)의 최대 단서를 정면으로 친다.
      "AUC 1.000 은 답을 1글자로 고정했기 때문 아니냐"에 답하려면
      답이 길어진 조건에서도 신호가 남는지 보여야 한다.

      그런데 실측해보니 더 고약한 문제가 있다 — 같은 지시를 줘도
      **추론을 많이 한 쪽이 답도 길게 쓴다**(sigfull: 755자 vs 534자).
      그래서 think_high 응답이 뚱뚱한 이유가 두 개가 된다:
        (1) 서명이 길어서  (2) 답이 길어서
      둘을 안 가르면 '추론 탐지'가 아니라 '긴 답 탐지'를 한 것이 된다.

핵심 방법 — 길이 보정 잔차:
      추론이 0인 콜만 써서 down_bytes = a*answer_chars + b 를 적합한다.
      이 콜들에는 서명이 없으므로(sig=98 고정) 이 직선은 순수한 '답 길이 → 바이트'
      변환이다. 그 직선으로 예측한 값을 빼면 남는 것이 서명 몫이다.
      잔차의 AUC 가 유지되면 "길이 때문이 아니다"가 증명된다.

입력: parse_pcap.py 가 만든 CSV 여러 개(arm 별). answer_chars·down_bytes·thoughts_tokens 필수.
출력: 표준출력. arm 별 분해표 + arm 간 비교표.
라벨 정하기 — provider 마다 조건이 다르다:
  Gemini : no_think 가 있어 '추론 0 vs >0' 이 자연스러운 이진이다(기본값).
  Groq   : no_think 가 없고 low/med/high 모두 추론한다(중앙 20/143/230).
           기본 라벨로는 음성 집단이 비어 평가가 안 되므로
           --split think_low,think_high 처럼 조건 두 개를 직접 지정한다.

사용: python3 len_control.py out/gem_sigtest.csv out/gem_sigbrief.csv out/gem_sigfull.csv
      python3 len_control.py out/groq_Alen0.csv out/groq_Alenbrief.csv out/groq_Alenfull.csv --split think_low,think_high
작성일: 2026-11-03
"""
import csv
import math
import argparse
import statistics as st


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _midranks(xs):
    """동점을 평균순위로. AUC·순위상관 양쪽에서 동점 처리가 필요하다."""
    n = len(xs)
    order = sorted(range(n), key=lambda k: xs[k])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def auc(scores, labels):
    n = len(scores)
    if n == 0:
        return None
    ranks = _midranks(scores)
    pos = [ranks[k] for k in range(n) if labels[k] == 1]
    n1, n0 = len(pos), n - len([1 for l in labels if l == 1])
    if n1 == 0 or n0 == 0:
        return None
    return (sum(pos) - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def fit_line(xs, ys):
    """최소제곱 직선. 점이 2개 미만이거나 x 분산이 0이면 기울기 0 + 평균."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)
    mx, my = sum(xs) / n, sum(ys) / n
    dx = sum((x - mx) ** 2 for x in xs)
    if dx == 0:
        return 0.0, my
    m = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / dx
    return m, my - m * mx


def _fmt(v, w=7, d=3):
    return ("-" if v is None else f"{v:.{d}f}").rjust(w)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        db = _num(r.get("down_bytes"))
        ac = _num(r.get("answer_chars"))
        if db is None or ac is None:
            continue
        # 토큰 한계에 걸려 잘린 콜은 답이 0자로 남아 층화를 망가뜨린다
        # (Groq Alen0 에서 '0~0자' 층이 생겼다). 분석에서 제외한다.
        if r.get("truncated") in ("1", "True", "true") or ac <= 0:
            continue
        out.append({
            "db": db,
            "ac": ac,
            "at": _num(r.get("answer_tokens")) or _num(r.get("output_tokens")),
            "th": _num(r.get("thoughts_tokens")) or 0.0,
            "sig": _num(r.get("sig_chars")),
            "gap": _num(r.get("pkt_gap_ms")),
            "stall": _num(r.get("stall_total_ms")),
            "imax": _num(r.get("down_iat_max_ms")),
            "cond": r.get("condition", ""),
        })
    return out


def analyze(path, label_name, split=None):
    R = load(path)
    if split:
        # 조건 기반 라벨. 두 번째 조건이 양성(= 더 깊은 추론 설정).
        R = [r for r in R if r["cond"] in split]
    print(f"\n\n{'#' * 78}")
    print(f"# {label_name}   ({path}, n={len(R)})")
    print(f"{'#' * 78}")
    if not R:
        print("빈 파일. 건너뜀.")
        return None

    if split:
        lab = [1 if r["cond"] == split[1] else 0 for r in R]
    else:
        lab = [1 if r["th"] > 0 else 0 for r in R]
    n1, n0 = sum(lab), len(lab) - sum(lab)
    if split:
        t1 = st.median([r["th"] for r, l in zip(R, lab) if l == 1])
        t0 = st.median([r["th"] for r, l in zip(R, lab) if l == 0])
        print(f"{split[1]} {n1}건 / {split[0]} {n0}건  (조건 기반 — 양쪽 다 추론은 한다)")
        print(f"    추론 토큰 중앙: {split[0]} {t0:.0f} / {split[1]} {t1:.0f}")
    else:
        print(f"추론함 {n1}건 / 추론안함 {n0}건")
    if n1 == 0 or n0 == 0:
        print("한쪽 클래스가 비어 평가 불가.")
        return None

    # --- 1. 답 길이가 라벨과 엮여 있나(교란의 크기) ---
    a1 = [r["ac"] for r, l in zip(R, lab) if l == 1]
    a0 = [r["ac"] for r, l in zip(R, lab) if l == 0]
    m1, m0 = st.median(a1), st.median(a0)
    auc_len = auc([r["ac"] for r in R], lab)
    print(f"\n[1] 답 길이 교란")
    pn, nn = (split[1], split[0]) if split else ("추론함", "추론안함")
    print(f"    {pn} 답 중앙 {m1:.0f}자 / {nn} {m0:.0f}자"
          f"  = {(m1 / m0 - 1) * 100:+.1f}%")
    print(f"    답 길이만으로 라벨 맞히기 AUC = {auc_len:.3f}"
          + ("   ← 길이만으로도 꽤 갈린다. 반드시 보정 필요"
             if auc_len and auc_len > 0.65 else "   (교란 약함)"))

    # --- 2. 보정 전 ---
    auc_db = auc([r["db"] for r in R], lab)
    auc_gap = auc([r["gap"] for r in R if r["gap"] is not None],
                  [l for r, l in zip(R, lab) if r["gap"] is not None])
    st_rows = [(r["stall"], l) for r, l in zip(R, lab) if r["stall"] is not None]
    auc_stall = auc([s for s, _ in st_rows], [l for _, l in st_rows]) if st_rows else None
    print(f"\n[2] 보정 전 — 관측자가 그냥 쓰는 값")
    im_rows = [(r["imax"], l) for r, l in zip(R, lab) if r["imax"] is not None]
    auc_imax = auc([v for v, _ in im_rows], [l for _, l in im_rows]) if im_rows else None
    # provider 마다 추론 침묵이 생기는 위치가 다르다(3-12).
    #   Gemini: 첫 응답 패킷 '전'  -> pkt_gap_ms 가 잡는다
    #   Groq  : 첫 응답 패킷 '뒤'  -> pkt_gap_ms 는 못 잡고 stall/iat_max 가 잡는다
    # 한 피처만 요약표에 올리면 Groq 이 "아무것도 안 샌다"로 잘못 읽힌다.
    cands = [("pkt_gap_ms", auc_gap), ("stall_total_ms", auc_stall),
             ("down_iat_max_ms", auc_imax)]
    best_t = max(((n, v) for n, v in cands if v is not None),
                 key=lambda kv: abs(kv[1] - 0.5), default=(None, None))
    print(f"    down_bytes       AUC {_fmt(auc_db)}")
    print(f"    pkt_gap_ms       AUC {_fmt(auc_gap)}   (추론 전 침묵 — Gemini 형)")
    print(f"    stall_total_ms   AUC {_fmt(auc_stall)}   (추론 후 정체 — Groq 형)")
    print(f"    down_iat_max_ms  AUC {_fmt(auc_imax)}")
    if best_t[0]:
        print(f"    -> 이 데이터의 최량 타이밍 피처: {best_t[0]} ({best_t[1]:.3f})")

    # --- 3. 길이 보정 잔차 ---
    # 음성 집단만으로 '답 길이 -> 바이트' 직선을 잡는다.
    #   기본(Gemini): 추론 0 콜. 서명이 98자 고정이라 서명 몫이 상수로 b 에 흡수된다.
    #   --split(Groq): 얕은 조건 콜. 추론량이 0은 아니지만 조건 안에서 거의 일정하므로
    #                  같은 논리가 근사적으로 성립한다. 깊은 조건의 '추가분'만 잔차로 남는다.
    bx = [r["ac"] for r, l in zip(R, lab) if l == 0]
    by = [r["db"] for r, l in zip(R, lab) if l == 0]
    m, b = fit_line(bx, by)
    resid = [r["db"] - (m * r["ac"] + b) for r in R]
    auc_res = auc(resid, lab)
    r1 = st.median([v for v, l in zip(resid, lab) if l == 1])
    r0 = st.median([v for v, l in zip(resid, lab) if l == 0])
    print(f"\n[3] 길이 보정 — 음성 집단으로 적합한 직선을 빼고 남은 것")
    print(f"    기준선: down_bytes = {m:.2f} × answer_chars + {b:.0f}"
          f"   ({(split[0] if split else '추론0')} {n0}건으로 적합)")
    print(f"    잔차 중앙  추론함 {r1:+.0f}바이트 / 추론안함 {r0:+.0f}바이트")
    print(f"    잔차        AUC {_fmt(auc_res)}", end="")
    if auc_res is not None and auc_db is not None:
        drop = auc_db - auc_res
        print(f"   (보정 전 대비 {drop:+.3f})")
        # 보정 '전'이 이미 우연 수준이면 잃을 신호가 없었던 것이다.
        # 그걸 "길이였다"로 찍으면 결론이 거꾸로 읽힌다(Groq free_brief 에서 발생).
        if auc_db < 0.6:
            print("    → 보정 전부터 우연 수준이다. 이 채널엔 애초에 신호가 없다")
            print("       (길이에 묻힌 게 아니라 원래 없었다는 뜻)")
        elif auc_res >= 0.95:
            print("    → 답 길이를 걷어내도 신호가 그대로다. '긴 답 탐지' 아님")
        elif auc_res >= 0.75:
            print("    → 신호가 줄었지만 남아 있다. 길이가 일부 기여했다")
        else:
            print("    → 신호 대부분이 답 길이였다. 주장 수정 필요")
    else:
        print()

    # --- 4. 층화: 답 길이가 비슷한 것끼리만 비교 ---
    # 잔차는 '선형'을 가정한다. 가정 없이 보려면 길이로 층을 나눠 층 안에서만 비교한다.
    print(f"\n[4] 층화 — 답 길이 4분위 안에서만 비교(선형 가정 없이)")
    acs = sorted(r["ac"] for r in R)
    cuts = [acs[int(len(acs) * p)] for p in (0.25, 0.50, 0.75)]

    def binof(x):
        return sum(1 for c in cuts if x >= c)

    tot_pairs = 0.0
    tot_conc = 0.0
    for q in range(4):
        sub = [(r, l) for r, l in zip(R, lab) if binof(r["ac"]) == q]
        s1 = [r["db"] for r, l in sub if l == 1]
        s0 = [r["db"] for r, l in sub if l == 0]
        rng = (f"{min(r['ac'] for r, _ in sub):.0f}~{max(r['ac'] for r, _ in sub):.0f}자"
               if sub else "-")
        if not s1 or not s0:
            print(f"    Q{q + 1} {rng:>14}  n={len(sub):>3}  "
                  f"추론 {len(s1)}/{len(s0)}  — 한쪽이 비어 평가 불가")
            continue
        a = auc(s1 + s0, [1] * len(s1) + [0] * len(s0))
        pairs = len(s1) * len(s0)
        tot_pairs += pairs
        tot_conc += a * pairs
        print(f"    Q{q + 1} {rng:>14}  n={len(sub):>3}  "
              f"추론 {len(s1)}/{len(s0)}  층내 AUC {_fmt(a)}")
    if tot_pairs:
        pooled = tot_conc / tot_pairs
        print(f"    층화 통합 AUC = {pooled:.3f}"
              + ("   ← 길이가 같아도 갈린다" if pooled >= 0.9 else ""))
    else:
        pooled = None

    # --- 5. 바이트 증가분 분해 ---
    if all(r["sig"] is not None for r in R):
        s1m = st.median([r["sig"] for r, l in zip(R, lab) if l == 1])
        s0m = st.median([r["sig"] for r, l in zip(R, lab) if l == 0])
        sig_share = (s1m - s0m) * 1.511
        len_share = (m1 - m0) * m
        tot = st.median([r["db"] for r, l in zip(R, lab) if l == 1]) - \
            st.median([r["db"] for r, l in zip(R, lab) if l == 0])
        print(f"\n[5] 바이트 증가분 분해 (중앙값 기준, 총 {tot:+.0f}바이트)")
        print(f"    서명 몫  {sig_share:+8.0f}바이트  "
              f"(sig {s0m:.0f}→{s1m:.0f}자 × 1.511)")
        print(f"    답   몫  {len_share:+8.0f}바이트  "
              f"(답 {m0:.0f}→{m1:.0f}자 × {m:.2f})")
        if tot:
            print(f"    비율     서명 {sig_share / tot * 100:.0f}% : "
                  f"답 {len_share / tot * 100:.0f}%")
    else:
        print("\n[5] sig_chars 열이 없어 분해 불가.")
        print("    Gemini 는 2026-10-30 이전 캡처라서, Groq 은 thoughtSignature 자체가")
        print("    없어서다. Groq 은 추론을 숨기고 서명도 안 보낸다 — 타이밍만 남는다.")

    return {"name": label_name, "n": len(R), "len_med": m0,
            "auc_len": auc_len, "auc_db": auc_db, "auc_res": auc_res,
            "auc_gap": auc_gap, "pooled": pooled,
            "best_t": best_t[1], "best_t_name": best_t[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--split", default=None,
                    help="조건 기반 라벨. '음성조건,양성조건' 형식. "
                         "예) --split think_low,think_high (Groq 처럼 no_think 가 없을 때)")
    a = ap.parse_args()
    split = None
    if a.split:
        parts = [s.strip() for s in a.split.split(",")]
        if len(parts) != 2:
            ap.error("--split 은 '음성조건,양성조건' 두 개여야 한다")
        split = tuple(parts)
    names = {"sigtest": "arm 0 — 답 1글자", "sigbrief": "arm free_brief — 답 ~150자",
             "sigfull": "arm free_full — 답 ~600자",
             "Alen0": "arm 0 — 답 1글자", "Alenbrief": "arm free_brief",
             "Alenfull": "arm free_full"}
    res = []
    for p in a.csv:
        key = next((k for k in names if k in p), None)
        out = analyze(p, names.get(key, p), split)
        if out:
            res.append(out)

    if len(res) > 1:
        print(f"\n\n{'=' * 78}")
        print("  arm 간 비교 — 답이 길어질수록 신호가 묻히나")
        print(f"{'=' * 78}")
        print(f"{'arm':<26}{'답중앙':>8}{'길이만':>8}{'바이트':>8}"
              f"{'잔차':>8}{'층화':>8}{'pkt_gap':>9}{'최량타이밍':>11}")
        for r in res:
            bt = f"{r['best_t']:.3f}" if r['best_t'] is not None else "-"
            print(f"{r['name']:<26}{r['len_med']:>7.0f}자"
                  f"{_fmt(r['auc_len'], 8)}{_fmt(r['auc_db'], 8)}"
                  f"{_fmt(r['auc_res'], 8)}{_fmt(r['pooled'], 8)}"
                  f"{_fmt(r['auc_gap'], 9)}{bt:>11}")
        for r in res:
            if r['best_t_name']:
                print(f"    ({r['name']} 의 최량 타이밍 = {r['best_t_name']})")
        print("\n  '길이만' = 답 길이만 보고 맞히기(교란 크기). 높을수록 보정이 중요하다.")
        print("  '잔차'·'층화' = 답 길이를 걷어낸 뒤의 탐지력. 바이트 채널에만 해당한다.")
        print("  'pkt_gap' 은 Gemini 형(추론 전 침묵) 전용이다. Groq 은 추론 침묵이")
        print("  첫 패킷 뒤에 와서 pkt_gap 으로는 안 보인다 — '최량타이밍' 열을 봐야 한다.")


if __name__ == "__main__":
    main()
