#!/usr/bin/env python3
"""
echo_fit.py — effort 문자열 에코가 전선 바이트에 '글자당 몇 바이트'로 찍히는지 잰다.

왜 필요한가
-----------
2026-11-24 에 OpenAI 응답이 effort 문자열("low"/"medium"/"high"/"xhigh"/"max")을
그대로 되돌려보내고, 그 길이가 `down_bytes` 에 그대로 실린다는 것을 찾았다.
500ms 창에서는 다른 피처가 거의 상수라 이 몇 바이트만으로 75% 가 나왔다 — 추론이 아니라
**라벨을 베낀 것**이다.

처방으로 `early_eval.py --quantize 100` 을 먼저 썼다. 그건 **라벨을 안 보는** 둔기라
안전하지만, 100바이트 버킷이 진짜 신호도 같이 깎아서 **하한**만 준다.
여기서는 에코의 크기를 **정확히 재서** 그만큼만 빼는 쪽을 만든다.

어떻게 재는가 — 같은 문항·둘 다 추론 0 인 조건 쌍
--------------------------------------------------
추론 토큰이 0 인 콜만 쓰면 조건 간 바이트 차이는 **원리적으로 추론일 수 없다**.
다만 그냥 모으면 선택 효과에 걸린다(low 에서 0 이 되는 문항은 가장 쉬운 것들이고
medium 에서 0 이 되는 문항은 더 넓다). 그래서 `leak_audit.py` 검사 A 와 똑같이
**같은 문항 안에서 둘 다 추론 0 인 조건 쌍**만 쓴다. 문항이 상수가 되므로 남는 차이는
설정 그 자체뿐이다.

쌍마다 Δ글자수(= STRLEN[조건B] - STRLEN[조건A])와 Δ피처값을 만들고,
**원점을 지나는** 최소제곱 기울기를 낸다(짝지은 차분이라 절편이 없다):

    k = Σ(Δx·Δy) / Σ(Δx²)

이상치에 둔한 추정치로 **Theil-Sen 중앙값**(median of Δy/Δx)도 같이 낸다.
둘이 크게 다르면 에코 말고 다른 것이 섞여 있다는 뜻이니 빼지 마라.

**주의 — 이 교정은 라벨을 본다**
--------------------------------
`--quantize` 는 조건을 모르고도 돌아간다(라벨 비의존). 반면 여기서 얻은 k 로
`down_bytes - k*len(effort)` 를 빼는 것은 **라벨을 쓴다**. k 가 틀리면 그 오차
`(k_true - k_hat) * len(effort)` 가 **다시 라벨에 정렬된 신호**로 남는다.
그래서 이 교정판 수치는 양자화판을 대체하는 게 아니라 **같이 보고하는 것**이다.
  - 양자화판 = 에코 제거 보장, 신호 일부 손실 → **하한**
  - 교정판   = 신호 보존, k 추정 오차가 라벨에 정렬될 위험 → **중간 추정**
  - 원본     = 에코 포함 → **상한**
k 가 정수에 딱 붙고(예: 2.00), R² 가 1 에 가깝고, 최소제곱과 Theil-Sen 이 일치할 때만
교정판을 믿어라. 그렇지 않으면 양자화판만 쓴다.

입력: out/early_<tag>.csv (cutoff_ms · condition · q_idx · thoughts_tokens 열 필요)
출력: 표준출력 표. --out 을 주면 CSV 로도 쓴다.
비용: 0

사용:
  python3 echo_fit.py out/early_luna250.csv
  python3 echo_fit.py out/early_*.csv --cutoff 500
  python3 echo_fit.py out/early_*.csv --out out/echo_k.csv

작성일: 2026-11-24
"""
import csv
import sys
import argparse

import numpy as np

# leak_audit.py / early_eval.py 와 같은 목록이어야 한다. 하나라도 다르면 비교가 안 된다.
WIRE = ["pkt_gap_ms", "up_pkts", "down_pkts", "up_bytes", "down_bytes",
        "down_pkt_mean", "down_pkt_max", "down_iat_mean_ms", "down_iat_max_ms",
        "down_iat_p90_ms", "down_iat_p99_ms", "stall_total_ms", "stall_count",
        "down_iat_first_ms", "n_pkts_window", "responded"]

ORD = ["think_low", "think_medium", "think_high", "think_xhigh", "think_max"]

# effort 문자열의 글자 수. 추론 깊이 순서(3<6<4<5<3)와 일치하지 않는다 —
# 그래서 '깊이를 읽은 것'과 '문자열을 읽은 것'을 구별할 수 있다.
STRLEN = {"think_low": 3, "think_medium": 6, "think_high": 4,
          "think_xhigh": 5, "think_max": 3}


def num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def thoughts(r):
    """추론 토큰. 빈칸은 0 이다.

    OpenAI 는 추론이 0 이면 usage 에서 필드를 통째로 빼버려 CSV 에 빈칸으로 들어온다.
    빈칸을 '모름' 으로 치면 추론 0 행이 하나도 안 남는다(2026-11-24 에 한 번 틀렸다).
    단 이 치환은 **직결 캡처에만** 안전하다 — 게이트웨이 경유분은 빈칸이 '안 알려줌'이라
    0 으로 접으면 전부 '추론 0' 으로 둔갑한다. 본 저장소 early_*.csv 는 전부 직결이다.
    """
    return num(r.get("thoughts_tokens"), 0.0)


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clean(rows):
    """early_eval.py 의 기본 `--clean-only` 와 **글자 그대로 같은** 필터.

    2026-11-25 에 여기서 틀렸다. 첫 판은 필터 없이 전부 넣고 k 를 쟀는데,
    Task A 75% 가 나온 모집단은 `early_eval.py` 의 기본 깨끗 부분집합이었다.
    모집단이 다르면 거기서 잰 k 로 저기를 교정할 수 없다 —
    거부·잘림·응답 길이 차이가 `down_bytes` 를 수백 바이트씩 흔들어
    R² 를 0.03 까지 떨어뜨렸다(terra250 최소제곱 143.9 대 중앙값 2.0).
    **교정은 교정할 대상과 같은 행에서 재야 한다.**
    """
    return [r for r in rows
            if r.get("complied") == "1" and r.get("truncated") == "0"
            and num(r.get("answer_chars"), -1) == 1]


def zero_pairs(rows):
    """같은 문항 안에서 둘 다 추론 0 인 조건 쌍. Δ글자수가 0 인 쌍은 버린다.

    Δ글자수 0 인 쌍(low↔max 는 둘 다 3글자)은 기울기 식의 분모에 0 을 넣을 뿐
    정보가 없다. 다만 **검증용으로는 쓸모가 있다** — 에코가 전부라면 그 쌍의
    Δ바이트는 0 이어야 한다. 그래서 따로 모아 돌려준다.
    """
    by_q = {}
    for r in rows:
        if thoughts(r) == 0:
            by_q.setdefault(r["q_idx"], {})[r["condition"]] = r
    pairs, ctrl = [], []
    for q, by_c in by_q.items():
        cs = [c for c in ORD if c in by_c]
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                ca, cb = cs[i], cs[j]
                dx = STRLEN[cb] - STRLEN[ca]
                (pairs if dx != 0 else ctrl).append((dx, by_c[ca], by_c[cb]))
    return pairs, ctrl, len(by_q)


def fit(pairs, feat, tol=1.0):
    """원점 통과 최소제곱 기울기 · Theil-Sen 중앙값 · R² · **적중률**.

    짝지은 차분이라 절편 항이 없다(같은 문항이므로 문항 고유분이 상쇄된다).

    2026-11-26 — R² 는 여기서 쓰면 안 되는 잣대다.
    ------------------------------------------------
    `1 - SSE/ΣΔy²` 로 재는데, 꼬리에 Δy 가 수천인 쌍이 몇 개만 있어도 분모가 그쪽으로
    채워진다. 쌍의 90% 가 정확히 2바이트/글자로 맞아도 R² 는 0 에 붙는다
    (terra250 500ms: Theil-Sen 2.00 인데 R² 0.002).
    결정론적 **바이트 에코**는 "평균적으로 비례" 가 아니라 "매번 정확히 같은 양" 이므로
    맞는 통계는 **적중률** — |Δy - k·Δx| <= tol 인 쌍의 비율 — 이다.
    R² 는 참고로만 남긴다.
    """
    dx = np.array([p[0] for p in pairs], dtype=float)
    dy = np.array([num(p[2].get(feat)) - num(p[1].get(feat)) for p in pairs],
                  dtype=float)
    sxx = float((dx * dx).sum())
    if sxx == 0:
        return None
    k = float((dx * dy).sum() / sxx)
    ts = float(np.median(dy / dx))
    sse = float(((dy - k * dx) ** 2).sum())
    sst = float((dy * dy).sum())
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    hit = float(np.mean(np.abs(dy - ts * dx) <= tol))
    # 비율의 최빈값 몇 개. 에코라면 한 값(예: 2.0)에 쌓인다.
    ratios = np.round(dy / dx, 2)
    vals, cnts = np.unique(ratios, return_counts=True)
    top = sorted(zip(cnts.tolist(), vals.tolist()), reverse=True)[:3]
    return k, ts, r2, hit, top, len(pairs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--cutoff", type=int, default=0,
                    help="검사할 cutoff_ms. 기본 0(전체 창)")
    ap.add_argument("--min-pairs", type=int, default=20,
                    help="추정을 시도할 최소 쌍 수")
    ap.add_argument("--feats", default="down_bytes,up_bytes",
                    help="자세히 볼 피처(쉼표). 비우면 WIRE 전부")
    ap.add_argument("--all", action="store_true",
                    help="WIRE 전 피처를 표에 올린다(어디까지 에코가 번졌는지 확인용)")
    # early_eval.py 와 같은 모집단에서 재야 거기서 뺄 수 있다. 기본 켜짐.
    ap.add_argument("--clean-only", action="store_true", default=True,
                    help="순응·비잘림·1글자 답만(기본). --no-clean-only 로 끈다")
    ap.add_argument("--no-clean-only", dest="clean_only", action="store_false")
    # 한쪽만 응답을 시작한 쌍은 Δ바이트가 '응답 유무' 를 재는 것이지 에코가 아니다.
    # 조기 창에서 특히 크게 튄다.
    ap.add_argument("--both-responded", action="store_true", default=True,
                    help="양쪽 다 응답을 시작한 쌍만(기본). --no-both-responded 로 끈다")
    ap.add_argument("--no-both-responded", dest="both_responded",
                    action="store_false")
    ap.add_argument("--tol", type=float, default=1.0,
                    help="적중 판정 허용오차(바이트). 기본 1 — 결정론적 에코면 0~1 이면 충분")
    ap.add_argument("--hit", type=float, default=0.60,
                    help="'에코 확정' 으로 볼 최소 적중률. 기본 0.60")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    feats = WIRE if a.all else [f.strip() for f in a.feats.split(",") if f.strip()]
    recs = []
    for path in a.csvs:
        rows = read(path)

        # 2026-11-26. parse_pcap 산출 wide CSV(out/gem_v2_all.csv 등)는 cutoff_ms 열이 없다.

        # 전체 창 한 줄짜리 long CSV 로 취급해 같은 코드로 감사한다.

        if rows and "cutoff_ms" not in rows[0]:

            for r in rows:

                r["cutoff_ms"] = "0"

                r.setdefault("responded", "1")

                r.setdefault("finished_by_cutoff", "1")

            print(f"[wide CSV] {path} — cutoff_ms 가 없어 전체 창으로 본다")
        if not rows or "thoughts_tokens" not in rows[0]:
            print(f"[건너뜀] {path} — thoughts_tokens 열이 없다")
            continue
        tag = path.split("early_")[-1].replace(".csv", "")
        g = [r for r in rows if int(num(r["cutoff_ms"])) == a.cutoff]
        if not g:
            print(f"[건너뜀] {tag} — cutoff {a.cutoff} 행이 없다")
            continue

        n_raw = len(g)
        if a.clean_only:
            g = clean(g)
        if a.both_responded:
            g = [r for r in g if num(r.get("responded")) == 1]
        pairs, ctrl, n_q = zero_pairs(g)
        lab = "전체 창" if a.cutoff == 0 else f"{a.cutoff}ms 창"
        print(f"\n########## {tag}   ({lab})   행 {n_raw} → {len(g)} "
              f"(clean={a.clean_only}, 양쪽응답={a.both_responded})")
        if len(pairs) < a.min_pairs:
            print(f"  쌍 {len(pairs)}개 (문항 {n_q}개) — {a.min_pairs}개 미만이라 추정 불가")
            continue
        print(f"  같은 문항·둘 다 추론 0 · Δ글자≠0 인 쌍 {len(pairs)}개 (문항 {n_q}개)"
              f"   Δ글자=0 대조쌍 {len(ctrl)}개")
        print(f"  {'피처':<20}{'k(중앙)':>9}{'적중률':>8}{'R²참고':>8}"
              f"   Δ/글자 최빈값(쌍수)        판정")
        for f in feats:
            r = fit(pairs, f, tol=a.tol)
            if r is None:
                continue
            k, ts, r2, hit, top, n = r
            # 판정은 **적중률**로 한다. R² 는 두꺼운 꼬리에서 0 으로 붕괴해 쓸 수 없다.
            #   k≈0 이고 적중률 높다  → 이 피처는 설정을 안 흘린다(깨끗)
            #   k≠0 이고 적중률 높다  → 결정론적 에코. 그만큼 빼면 된다
            #   적중률 낮다           → 다른 분산이 지배. 빼지 말고 양자화를 써라
            if hit < a.hit:
                verdict = "분산 지배 — 빼지 마라(양자화)"
            elif abs(ts) < 0.5:
                verdict = "깨끗 — 에코 없음"
            else:
                verdict = f"에코 확정 — {ts:g}x글자수 빼라"
            tops = " ".join(f"{v:g}({c})" for c, v in top)
            print(f"  {f:<20}{ts:>9.2f}{100*hit:>7.1f}%{r2:>8.3f}   "
                  f"{tops:<24}{verdict}")
            recs.append({"tag": tag, "cutoff_ms": a.cutoff, "feat": f,
                         "k_ls": round(k, 4), "k_theilsen": round(ts, 4),
                         "hit_rate": round(hit, 4), "r2": round(r2, 4),
                         "n_pairs": n})

        # Δ글자=0 대조. 에코가 전부라면 이 쌍의 Δ바이트 중앙값은 0 이어야 한다.
        # 0 이 아니면 글자 수 말고 **다른 것**이 조건을 따라 움직이고 있다는 뜻이다.
        if ctrl:
            print("  [대조] Δ글자=0 인 쌍(low↔max)의 Δ 중앙값 — 에코뿐이라면 0 이어야 한다")
            line = []
            for f in feats:
                d = [num(p[2].get(f)) - num(p[1].get(f)) for p in ctrl]
                line.append(f"{f}={np.median(d):.1f}")
            print("          " + "  ".join(line) + f"   (쌍 {len(ctrl)}개)")

    if a.out and recs:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
            w.writeheader()
            w.writerows(recs)
        print(f"\n[out] {a.out}  ({len(recs)}행)")

    print("\n→ '에코 확정' 인 피처만 early_eval.py --echo-sub 로 빼라.")
    print("→ 교정판은 양자화판을 대체하지 않는다. 원본(상한)·양자화(하한)과 **같이** 적어라.")


if __name__ == "__main__":
    sys.exit(main())
