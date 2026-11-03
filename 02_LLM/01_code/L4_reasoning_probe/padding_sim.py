"""
padding_sim.py — 버킷 패딩 방어 시뮬레이션: 길이 누출을 얼마나 싸게 막을 수 있나.

짝 스크립트: defense_sim.py (2026-10-02) 는 피처를 통째로 제거해(채널 차단)
분류 정확도가 얼마나 떨어지는지를 재고, 지연 균일화도 다룬다.
이 스크립트는 그보다 현실적인 방어를 본다 — 채널을 없애는 게 아니라
버킷으로 올림했을 때 AUC 가 얼마나 떨어지고 대역폭을 얼마나 더 쓰는가.

목적: 3-16에서 확인한 "추론량 -> thoughtSignature 길이 -> 응답 바이트" 누출을
      패딩으로 막았을 때 (1) 탐지력이 얼마나 떨어지고 (2) 대역폭을 얼마나 더 쓰는지
      기존 CSV 만으로 계산한다. 새 캡처 불필요.

      논점은 "우리가 뚫었다"가 아니라 "이렇게 싸게 막히는데 왜 아직 안 막나"이므로,
      방어 비용을 공격자인 우리가 먼저 숫자로 내놓는 것이 이 스크립트의 존재 이유다.

핵심 주의: 패딩은 '크기' 채널만 죽인다. 추론 중 침묵(타이밍)은 그대로 남는다.
           그래서 타이밍 AUC 를 '패딩이 건드리지 못하는 바닥'으로 같이 출력한다.

입력: parse_pcap.py 가 만든 CSV (down_bytes, thoughts_tokens 필수.
      sig_chars 있으면 방어 (A) 도 평가, pkt_gap_ms 있으면 타이밍 바닥도 출력)
출력: 표준출력 표 (버킷 크기별 AUC / 상관 / 오버헤드)
사용: python3 padding_sim.py out/gem_sigtest.csv
작성일: 2026-11-03
"""
import sys
import csv
import math
import argparse
import statistics as st


def _num(v):
    """CSV 셀 -> float. 빈칸/None 은 None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _midranks(xs):
    """동점을 평균순위로 처리한 순위 벡터.

    패딩을 세게 걸면 값이 전부 같은 버킷으로 뭉쳐 동점이 대량 발생한다.
    동점을 순차순위로 처리하면 AUC 가 0.5 가 아니라 엉뚱한 값으로 나와
    "방어가 덜 먹혔다"는 가짜 결론이 나온다. 반드시 midrank 로 처리할 것.
    """
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
    """이진 라벨에 대한 AUC(Mann-Whitney U). 동점은 midrank 로 0.5 기여."""
    n = len(scores)
    ranks = _midranks(scores)
    pos = [ranks[k] for k in range(n) if labels[k] == 1]
    n1 = len(pos)
    n0 = n - n1
    if n1 == 0 or n0 == 0:
        return None
    return (sum(pos) - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def spearman(a, b):
    """순위상관. 동점 midrank 처리."""
    ra, rb = _midranks(a), _midranks(b)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    sn = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((x - mb) ** 2 for x in rb))
    return sn / (da * db) if da and db else None


def pad_block(v, b):
    """다음 b 배수로 올림. 가장 단순하고 가장 흔한 패딩."""
    return math.ceil(v / b) * b


def pad_pow2(v):
    """다음 2의 거듭제곱으로 올림. 버킷이 커질수록 오버헤드도 같이 커진다."""
    p = 1
    while p < v:
        p *= 2
    return p


def overhead(orig, padded, wire=None, slope=1.0):
    """추가량과 증가율(%).

    wire 가 주어지면 증가율을 '응답 전체 바이트' 기준으로 계산한다.
    왜 필요한가 — 서명만 패딩하는 방어(A)의 증가율을 서명 길이(기준선 98자)로 나누면
    +1178% 같은 숫자가 나오는데, 이건 대역폭 비용이 아니라 '서명이 몇 배 됐나'일 뿐이다.
    방어(B)의 응답 전체 기준 증가율과 분모가 달라 그대로 비교하면 (A)가 20배 비싼
    것처럼 보이는 착시가 생긴다. 실제 청구서는 둘 다 '응답 총 바이트'로 날아온다.
    slope 는 앱 계층 1단위가 wire 몇 바이트인지(서명은 3-16 실측 1.511).
    """
    add = [(q - o) for o, q in zip(orig, padded)]
    if wire is not None:
        pct = [(q - o) * slope / w * 100
               for o, q, w in zip(orig, padded, wire) if w > 0]
        return st.mean(add), st.mean(pct)
    pct = [(q - o) / o * 100 for o, q in zip(orig, padded) if o > 0]
    return st.mean(add), st.mean(pct)


def sweep(vals, labels, toks, name, unit, wire=None, slope=1.0):
    """버킷 크기를 쓸면서 AUC / 순위상관 / 오버헤드를 표로 찍는다.

    AUC   = '추론을 했나 안 했나' 탐지력 (0.5 = 완전 무력화)
    순위상관 = '얼마나 했나' 해상도 누출 (0 = 완전 무력화)
    증가율 = wire 가 주어지면 응답 전체 바이트 대비(방어 간 비교 가능한 분모)
    """
    au = "자" if unit == "문자" else "B"
    denom = "응답전체" if wire is not None else "자기자신"
    print(f"\n{'='*74}")
    print(f"  {name}  (단위 {unit})")
    print(f"{'='*74}")
    base_auc = auc(vals, labels)
    base_rho = spearman(vals, toks) if toks else None
    print(f"{'버킷':>8} {'AUC':>7} {'순위상관':>9} {'추가량':>10} "
          f"{'증가율':>8} {'고유값':>7}   (증가율 분모={denom})")
    print(f"{'없음':>8} {base_auc:>7.3f} "
          f"{(f'{base_rho:.3f}' if base_rho is not None else '-'):>9} "
          f"{'-':>10} {'-':>8} {len(set(vals)):>7}")

    rows = []
    for b in [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]:
        pv = [pad_block(v, b) for v in vals]
        a = auc(pv, labels)
        r = spearman(pv, toks) if toks else None
        add, pct = overhead(vals, pv, wire, slope)
        rows.append((b, a, r, add, pct, len(set(pv))))
        print(f"{b:>8} {a:>7.3f} "
              f"{(f'{r:.3f}' if r is not None else '-'):>9} "
              f"{add:>9.0f}{au} {pct:>7.1f}% {len(set(pv)):>7}")

    pv = [pad_pow2(v) for v in vals]
    a = auc(pv, labels)
    r = spearman(pv, toks) if toks else None
    add, pct = overhead(vals, pv, wire, slope)
    print(f"{'2^k':>8} {a:>7.3f} "
          f"{(f'{r:.3f}' if r is not None else '-'):>9} "
          f"{add:>9.0f}{au} {pct:>7.1f}% {len(set(pv)):>7}")

    mx = max(vals)
    pv = [mx] * len(vals)
    add, pct = overhead(vals, pv, wire, slope)
    print(f"{'최대고정':>8} {0.5:>7.3f} {0.0:>9.3f} {add:>9.0f}{au} {pct:>7.1f}% {1:>7}")
    print("  ('최대고정' = 전부 최댓값으로 맞춤. 완벽 방어이자 비용 상한)")

    # 실무적으로 의미 있는 임계를 넘는 최소 버킷을 짚어준다.
    for target in (0.70, 0.60, 0.55):
        hit = next((b for b, a, *_ in rows if a <= target), None)
        if hit:
            o = next(q for b, a, r, ad, q, u in rows if b == hit)
            print(f"  AUC <= {target:.2f} 까지 떨어뜨리려면 버킷 {hit}{au} "
                  f"(대역폭 +{o:.1f}%, {denom} 대비)")
        else:
            print(f"  AUC <= {target:.2f} : 시험한 버킷 범위에서 도달 못 함")
    return base_auc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="parse_pcap.py 출력 CSV")
    ap.add_argument("--sig-slope", type=float, default=1.511,
                    help="sig_chars -> down_bytes 기울기(3-16 실측 1.511)")
    a = ap.parse_args()

    for path in a.csv:
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        print(f"\n\n{'#'*74}")
        print(f"# {path}   ({len(rows)}행)")
        print(f"{'#'*74}")

        # 라벨: 추론을 실제로 했나(realized). configured 조건이 아니라 토큰 수 기준.
        # Gemini no_think 는 thoughts_tokens 가 빈칸으로 오므로 0 으로 읽는다.
        recs = []
        for r in rows:
            db = _num(r.get("down_bytes"))
            if db is None:
                continue
            th = _num(r.get("thoughts_tokens")) or 0.0
            recs.append({
                "db": db, "th": th,
                "sig": _num(r.get("sig_chars")),
                "gap": _num(r.get("pkt_gap_ms")),
                "cond": r.get("condition", ""),
            })
        labels = [1 if r["th"] > 0 else 0 for r in recs]
        # 버킷 패딩의 한계는 '동적 범위'가 결정한다. 값이 버킷보다 크면 버킷이 여러 개로
        # 갈라져 그 구간은 그대로 샌다. 완전히 가리려면 버킷 >= 최댓값이어야 하고,
        # 따라서 비용은 평균이 아니라 '최악의 경우'가 정한다. 이 비율을 먼저 찍어둔다.
        dbv = [r["db"] for r in recs]
        print(f"down_bytes 동적 범위: {min(dbv):.0f} ~ {max(dbv):.0f} "
              f"= {max(dbv)/min(dbv):.1f}배")
        sv = [r["sig"] for r in recs if r["sig"] is not None]
        if sv:
            print(f"sig_chars  동적 범위: {min(sv):.0f} ~ {max(sv):.0f} "
                  f"= {max(sv)/min(sv):.1f}배")
        toks = [r["th"] for r in recs]
        n1, n0 = sum(labels), len(labels) - sum(labels)
        print(f"추론함 {n1}건 / 추론안함 {n0}건")
        if n1 == 0 or n0 == 0:
            print("한쪽 클래스가 비어 평가 불가. 건너뜀.")
            continue

        # (B) 응답 전체 패딩 — 모델 없이 실측 바이트를 그대로 올림. 무차별·고비용.
        sweep([r["db"] for r in recs], labels, toks,
              "방어 (B) 응답 전체 패딩 — 실측 down_bytes", "바이트")

        # (A) 서명만 패딩 — 새는 필드 하나만 올림. 표적형·저비용.
        if all(r["sig"] is not None for r in recs):
            sig = [r["sig"] for r in recs]
            sweep(sig, labels, toks,
                  "방어 (A) thoughtSignature 만 패딩 — 앱 계층", "문자",
                  wire=[r["db"] for r in recs], slope=a.sig_slope)
            # 앱 계층 패딩이 wire 에서 얼마짜리인지 환산(기울기는 3-16 회귀값).
            base = st.mean([r["db"] - a.sig_slope * r["sig"] for r in recs])
            print(f"\n  [환산] 서명 1문자 = wire {a.sig_slope:.3f}바이트, "
                  f"서명 외 고정분 평균 {base:.0f}바이트")
            print(f"  즉 앱 계층에서 서명을 B문자 버킷으로 올리면 "
                  f"wire 비용은 최대 {a.sig_slope:.2f}×B 바이트.")
        else:
            print("\n[건너뜀] sig_chars 열이 없어 방어 (A) 평가 불가 "
                  "(2026-10-30 이전 캡처는 계측 전).")

        # 패딩이 건드리지 못하는 바닥 — 타이밍.
        gaps = [(r["gap"], l) for r, l in zip(recs, labels) if r["gap"] is not None]
        if len(gaps) >= 10:
            ga = auc([g for g, _ in gaps], [l for _, l in gaps])
            print(f"\n{'='*74}")
            print("  패딩이 못 막는 부분 — 타이밍 채널")
            print(f"{'='*74}")
            print(f"  pkt_gap_ms 단독 AUC = {ga:.3f}  (n={len(gaps)})")
            print("  이 값은 어떤 패딩을 걸어도 그대로다. 바이트를 0.5 로 눌러도")
            print("  여기가 바닥으로 남는다. 타이밍까지 막으려면 지연 삽입이 필요하고,")
            print("  그건 대역폭이 아니라 응답속도를 내주는 것이라 비용 성격이 다르다.")


if __name__ == "__main__":
    main()
