#!/usr/bin/env python3
"""sig_corr.py — 캡처 로그(jsonl)에서 "추론 토큰 <-> 서명 글자수" 상관을 잰다.

왜: Gemini thoughtSignature 는 추론 내용을 숨기면서 그 암호화 blob 의 길이는
    그대로 노출한다(토큰과 Pearson 0.982). TLS 는 길이를 가리지 않으므로
    이 비례가 성립하면 하향 바이트만으로 추론량이 샌다. 다른 제조사에도
    같은 구조가 있는지를, 본 캡처(비싸다) 전에 싸게 확인하는 용도다.

입력: 캡처 러너가 쓴 jsonl. thoughts_tokens, sig_chars, condition 필드를 쓴다.
출력: 전체 Pearson/Spearman/회귀 + 조건별 중앙값 표 + 콜당 평균 출력토큰(비용 추정용)
사용: python3 sig_corr.py out/anth_sigprobe_log.jsonl
작성일: 2026-11-18
"""
import json
import sys
from statistics import median


def pearson(x, y):
    """원값 그대로의 직선 관계. 이상치 하나에 크게 흔들린다."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return 0.0, 0.0, my          # 한쪽이 상수면 상관이 정의되지 않는다
    slope = sxy / sxx
    return sxy / (sxx * syy) ** 0.5, slope, my - slope * mx


def ranks(v):
    """순위로 바꾼다(동점은 평균순위). 여기에 pearson 을 먹이면 스피어만이다."""
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit("사용: python3 sig_corr.py <로그.jsonl>")
    rows = []
    with open(sys.argv[1], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    err = [r for r in rows if r.get("error")]
    ok = [r for r in rows
          if not r.get("error")
          and r.get("thoughts_tokens") is not None
          and r.get("sig_chars") is not None]
    print(f"행 {len(rows)}  성공 {len(ok)}  실패 {len(err)}")
    if err:
        print("  첫 실패:", str(err[0]["error"])[:120])
    if len(ok) < 3:
        raise SystemExit("점이 모자라 상관을 못 낸다.")

    x = [r["thoughts_tokens"] for r in ok]
    y = [r["sig_chars"] for r in ok]
    r_p, slope, icept = pearson(x, y)
    r_s, _, _ = pearson(ranks(x), ranks(y))
    print(f"\n전체 n={len(ok)}")
    print(f"  Pearson  {r_p:.4f}")
    print(f"  Spearman {r_s:.4f}")
    print(f"  회귀     서명 = {slope:.3f} * 추론토큰 + {icept:.1f}")
    print(f"  추론토큰 {min(x)} ~ {max(x)}   서명 {min(y)} ~ {max(y)}")
    zero = sum(1 for v in y if v == 0)
    if zero:
        print(f"  ! 서명 0 인 콜 {zero}개 — 누출 경로가 조건부다")

    # 조건별. 단계가 올라가면 추론과 서명이 같이 커지는지 본다.
    by = {}
    for r in ok:
        by.setdefault(r.get("condition", "?"), []).append(r)
    print("\n조건           n   추론토큰(중앙)  서명(중앙)   비율")
    for k, g in by.items():
        mt = median(r["thoughts_tokens"] for r in g)
        ms = median(r["sig_chars"] for r in g)
        ratio = f"{ms / mt:.2f}" if mt else "-"
        print(f"{k:<14} {len(g):>2}   {mt:>12}   {ms:>9}   {ratio}")

    # 본 캡처 비용 추정용. 출력 토큰에 추론이 포함되므로 그대로 쓰면 된다.
    out_tok = sum(r.get("output_tokens") or 0 for r in ok) / len(ok)
    print(f"\n콜당 평균 출력토큰 {out_tok:.0f} (추론 포함)")


if __name__ == "__main__":
    main()
