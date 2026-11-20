#!/usr/bin/env python3
"""wire_check.py — 캡처 CSV 의 "요청 길이 통제"가 전선에서 성립했는지 검사한다.

왜: 조건(추론 단계)별로 요청 바이트가 다르면, 분류기가 추론이 아니라 요청 크기를
    보고 맞히게 된다. 프롬프트 패딩이 그걸 막는 장치인데, 실제로 먹었는지는
    pcap 을 봐야 안다. 애플리케이션 계층의 input_tokens 는 토크나이저 경계 때문에
    조건별로 1~2 토큰씩 달라도 바이트는 같을 수 있어, 토큰으로 판정하면 안 된다.

주의: 조건 전체의 중앙값만 비교하면 안 된다. 재전송이 난 칸 하나가 정렬 순서를
    밀어 중앙값을 바꾼다(2026-11-18 luna 배선 확인에서 "17바이트 차이"가 그랬다).
    그래서 **문항 안에서** 조건끼리 비교한다.

입력: parse_pcap.py 가 쓴 CSV (q_idx, condition, up_bytes, up_pkts, down_bytes 필요)
출력: 문항별 일치 여부 + 어긋난 칸 목록 + 조건별 down_bytes 중앙값
사용: python3 wire_check.py out/openai_wiretest.csv
작성일: 2026-11-18
"""
import csv
import sys
from collections import defaultdict
from statistics import median


def main():
    if len(sys.argv) < 2:
        raise SystemExit("사용: python3 wire_check.py <캡처.csv>")
    rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
    if not rows:
        raise SystemExit("빈 CSV")

    def num(r, k):
        try:
            return int(float(r[k]))
        except (KeyError, ValueError, TypeError):
            return None

    # 문항별로 묶어 조건끼리 up_bytes 를 비교한다.
    byq = defaultdict(dict)
    for r in rows:
        ub = num(r, "up_bytes")
        if ub is None:
            continue
        byq[r["q_idx"]][r["condition"]] = (ub, num(r, "up_pkts"), num(r, "down_bytes"))

    same, diff, bad = 0, 0, []
    for q, conds in byq.items():
        ups = {c: v[0] for c, v in conds.items()}
        if len(set(ups.values())) == 1:
            same += 1
            continue
        diff += 1
        # 최빈값에서 벗어난 칸만 지목한다. 보통 재전송 한 칸이다.
        counts = defaultdict(int)
        for v in ups.values():
            counts[v] += 1
        base = max(counts, key=lambda k: (counts[k], -k))
        for c, v in ups.items():
            if v != base:
                bad.append((q, c, v, base, conds[c][1]))

    print(f"문항 {len(byq)}  조건 {len(set(r['condition'] for r in rows))}  행 {len(rows)}")
    print(f"up_bytes 가 조건 간 완전히 같은 문항: {same} / {len(byq)}")
    if diff:
        print(f"\n어긋난 칸 {len(bad)}개 (q_idx, 조건, 그 칸, 그 문항의 기준값, up_pkts):")
        for q, c, v, base, pk in sorted(bad):
            # up_pkts 가 기준보다 많으면 TCP 재전송이다. 패딩 버그가 아니다.
            note = "  <- 재전송으로 보인다(up_pkts 과다)" if (pk or 0) > 2 else ""
            print(f"  q{q:>5}  {c:<14} {v:>6}  기준 {base:>6}  up_pkts {pk}{note}")
        print("\n판정: 어긋난 칸이 재전송뿐이면 통제는 성립한다. 분석에서 그 칸만 빼라.")
        print("      재전송이 아닌데 조건별로 일정하게 어긋나면 패딩 버그다.")
    else:
        print("\n판정: 통제 성립. 요청 바이트가 조건을 구분하지 않는다.")

    # 하향 바이트는 반대로 조건에 따라 벌어져야 한다 — 그게 신호다.
    down = defaultdict(list)
    for r in rows:
        d = num(r, "down_bytes")
        if d is not None:
            down[r["condition"]].append(d)
    print("\n조건별 down_bytes 중앙값 (벌어져야 정상 — 이게 신호다)")
    for c in sorted(down, key=lambda k: median(down[k])):
        print(f"  {c:<14} {median(down[c]):>9.0f}   n={len(down[c])}")


if __name__ == "__main__":
    main()
