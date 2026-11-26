#!/usr/bin/env python3
"""조기 탐지(RQ6): 응답이 끝나기 전에 얼마나 일찍 판단할 수 있는가.

왜 필요한가
-----------
지금까지의 모든 수치는 **응답이 끝난 뒤** 전체 측정창으로 잰 것이다. 실제 공격자는
세션이 끝날 때까지 기다릴 수도 있지만, 조기에 판단할 수 있으면 위협이 훨씬 커진다
(실시간 차단·우선순위 조정·과금 추정 등이 가능해진다).

핵심은 **작은 시각에서는 '없음'이 신호**라는 점이다. Claude opus 의 TTFT 중앙값이
약 3초이므로, 요청 500ms 시점에 하향 데이터가 한 바이트도 없다는 사실 자체가
"아직 생각 중"을 뜻한다. 그래서 빈 창을 결측으로 두지 않고 0 과 플래그로 기록한다.

무엇을 하는가
-------------
기존 pcap 을 **다시 찍지 않고** 재파싱한다. 측정창의 끝을 t_start + cutoff 로 잘라
parse_pcap.py 와 **같은 피처**를 계산하고, cutoff 마다 한 행씩 긴 형식으로 낸다.
cutoff 0 은 자르지 않은 전체 창이라 parse_pcap.py 결과와 대조할 수 있다.

입력 : pcap, JSONL 로그(parse_pcap.py 와 같은 쌍)
출력 : --out CSV. 열에 cutoff_ms 가 추가된 long 형식
비용 : 0. API 콜을 한 개도 보내지 않는다.

사용:
    python3 early_detect.py out/openai_strict_sol250_*.pcap \\
        out/openai_strict_sol250_log.jsonl --local-ip 163.152.223.17 \\
        --out out/early_sol250.csv

    # cutoff 를 직접 지정 (ms). 0 = 전체 창
    python3 early_detect.py ... --cutoffs 200,500,1000,2000,5000,10000,0

작성일: 2026-11-20
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics as st
from pathlib import Path

from scapy.all import rdpcap, IP, TCP

# parse_pcap.py 와 같은 값. 전체 창을 쓸 때 응답 꼬리 패킷을 포함하기 위한 여유.
BUFFER_S = 1.0
# parse_pcap.py 와 같은 '정체' 기준.
STALL_MS = 100.0
# 기본 cutoff. 0 은 자르지 않음(전체). TTFT 분포가 수백 ms ~ 수십 초라 로그 간격으로 잡는다.
DEFAULT_CUTOFFS = "200,500,1000,2000,5000,10000,0"


def load_entries(log_path: str) -> list[dict]:
    """JSONL 로그에서 쓸 수 있는 요청만 고른다. parse_pcap.py 와 같은 기준."""
    out = []
    with open(log_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("error") or not e.get("t_start"):
                continue
            e.setdefault("idx", i)
            out.append(e)
    return out


def features(win: list, local_ip: str) -> dict:
    """측정창 패킷 목록 → 전선 피처. parse_pcap.py 의 계산과 같게 유지한다.

    창이 비어 있어도 None 이 아니라 0 을 낸다. 조기 탐지에서는 '아직 아무것도 안 왔다'가
    결측이 아니라 가장 강한 신호이기 때문이다. 결측으로 두면 분류기가 그 행을 버린다.
    """
    out = [r for r in win if r[1] == local_ip and r[3] > 0]   # client -> server
    inc = [r for r in win if r[2] == local_ip and r[3] > 0]   # server -> client

    t_req = out[0][0] if out else None
    t_resp = None
    if t_req is not None:
        later = [r for r in inc if r[0] >= t_req]
        t_resp = later[0][0] if later else None

    down_sizes = [r[3] for r in inc]
    down_times = sorted(r[0] for r in inc)
    iats = [(down_times[i + 1] - down_times[i]) * 1000 for i in range(len(down_times) - 1)]
    iats_sorted = sorted(iats)

    def _pct(p):
        if not iats_sorted:
            return 0.0
        k = min(len(iats_sorted) - 1, int(len(iats_sorted) * p))
        return round(iats_sorted[k], 1)

    stalls = [v for v in iats if v >= STALL_MS]
    return {
        "pkt_gap_ms": round((t_resp - t_req) * 1000, 1) if (t_req and t_resp) else None,
        "up_pkts": len(out), "down_pkts": len(inc),
        "up_bytes": sum(r[3] for r in out), "down_bytes": sum(r[3] for r in inc),
        "down_pkt_mean": round(st.mean(down_sizes), 1) if down_sizes else 0.0,
        "down_pkt_max": max(down_sizes) if down_sizes else 0,
        "down_iat_mean_ms": round(st.mean(iats), 1) if iats else 0.0,
        "down_iat_max_ms": round(max(iats), 1) if iats else 0.0,
        "down_iat_p90_ms": _pct(0.90),
        "down_iat_p99_ms": _pct(0.99),
        "stall_total_ms": round(sum(stalls), 1) if iats else 0.0,
        "stall_count": len(stalls),
        "down_iat_first_ms": round(iats[0], 1) if iats else 0.0,
        "n_pkts_window": len(win),
        # 조기 탐지의 핵심 플래그. 작은 cutoff 에서는 이것 하나가 대부분의 정보다.
        "responded": 1 if inc else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcap")
    ap.add_argument("log")
    ap.add_argument("--local-ip", required=True,
                    help="캡처한 쪽 IP. 방향(상향/하향)을 가르는 기준이라 틀리면 전부 뒤집힌다")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cutoffs", default=DEFAULT_CUTOFFS,
                    help="요청 시작으로부터 몇 ms 까지 볼지(쉼표). 0 = 자르지 않음")
    a = ap.parse_args()

    cutoffs = [int(x.strip()) for x in a.cutoffs.split(",") if x.strip()]
    entries = load_entries(a.log)
    print(f"요청 {len(entries)}개  cutoff {cutoffs}")

    print("pcap 읽는 중...")
    pkts = rdpcap(a.pcap)
    recs = []
    for p in pkts:
        if IP in p and TCP in p:
            recs.append((float(p.time), p[IP].src, p[IP].dst, len(p[TCP].payload)))
    recs.sort()
    times = [r[0] for r in recs]
    print(f"패킷 {len(recs)}개")

    rows = []
    for e in entries:
        t0 = e["t_start"]
        t_end_full = (e.get("t_end") or t0) + BUFFER_S
        # 전체 창을 한 번만 잘라 두고, cutoff 마다 그 안에서 다시 자른다.
        # 선형 탐색이면 요청 수 x 패킷 수라 느려서 정렬된 시각에 이분 탐색을 쓴다.
        lo = bisect.bisect_left(times, t0)
        hi_full = bisect.bisect_right(times, t_end_full)
        win_full = recs[lo:hi_full]

        dur_ms = ((e.get("t_end") or t0) - t0) * 1000.0
        for cut in cutoffs:
            if cut <= 0:
                win = win_full
                cut_label = 0
                done = 1
            else:
                t1 = min(t0 + cut / 1000.0, t_end_full)
                hi = bisect.bisect_right(times, t1, lo, hi_full)
                win = recs[lo:hi]
                cut_label = cut
                # 이 시점에 응답이 이미 끝나 있었나. 끝난 콜은 '조기'가 아니라
                # 그냥 전체를 본 것이므로 분석에서 따로 다뤄야 한다.
                done = 1 if dur_ms <= cut else 0
            f = features(win, a.local_ip)
            f.update({
                "idx": e["idx"], "q_idx": e["q_idx"], "condition": e["condition"],
                "family": e.get("family") or f"q{e['q_idx']}",
                "rep": e.get("rep", 0), "arm": e.get("arm"),
                "cutoff_ms": cut_label,
                # 이 시각까지 응답이 끝났는지(1) 아직 진행 중이었는지(0).
                "finished_by_cutoff": done,
                # 전체 소요시간 대비 본 비율. 1.0 이면 사실상 전체를 본 것.
                "seen_frac": round(min(1.0, (cut / dur_ms)) if (cut > 0 and dur_ms > 0) else 1.0, 3),
                "total_ms": round(dur_ms, 1),
                # 라벨·대조용(공격자는 못 보는 값).
                "thoughts_tokens": e.get("thoughts_tokens"),
                "answer_chars": e.get("answer_chars"),
                "truncated": 1 if e.get("truncated") else 0,
                "complied": 1 if e.get("complied") else 0,
                "sig_chars": e.get("sig_chars"),
                "app_ttft_ms": e.get("app_ttft_ms"),
            })
            rows.append(f)

    if not rows:
        raise SystemExit("행이 하나도 안 나왔다. --local-ip 와 pcap/log 짝을 확인하라.")

    cols = list(rows[0].keys())
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\n[out] {a.out}  ({len(rows)}행 = 요청 {len(entries)} x cutoff {len(cutoffs)})")

    # cutoff 별 요약. '그 시점에 응답이 시작조차 안 한 비율'이 조기 탐지의 출발점이다.
    print(f"\n{'cutoff':>8} {'응답시작%':>9} {'이미완료%':>9} {'down_bytes중앙':>14} {'본비율중앙':>10}")
    for cut in cutoffs:
        g = [r for r in rows if r["cutoff_ms"] == cut]
        if not g:
            continue
        resp = 100.0 * sum(r["responded"] for r in g) / len(g)
        fin = 100.0 * sum(r["finished_by_cutoff"] for r in g) / len(g)
        db = sorted(r["down_bytes"] for r in g)[len(g) // 2]
        sf = sorted(r["seen_frac"] for r in g)[len(g) // 2]
        lab = "전체" if cut == 0 else f"{cut}ms"
        print(f"{lab:>8} {resp:>8.1f}% {fin:>8.1f}% {db:>14} {sf:>10.2f}")
    print("\n→ 응답시작%가 조건별로 갈리면, 그 시점엔 '침묵' 자체가 신호다.")
    print("→ 이미완료%가 높은 cutoff 는 조기 탐지가 아니라 전체 관측에 가깝다. 해석 주의.")


if __name__ == "__main__":
    main()
