"""
parse_pcap_rich.py — pcap에서 피처를 대폭 늘려 뽑는다(약 130개). parse_pcap.py 의 확장판.

왜 만들었나:
  기존 parse_pcap.py 는 집계 피처를 6개만 뽑았다(침묵·상하향 바이트/패킷수·간격평균·크기평균/최대).
  그런데 provider 마다 추론이 트래픽에 남는 자리가 달랐다.
    Gemini : 추론 시간이 첫 침묵에 쌓이고, 추론량이 응답 바이트로도 샌다.
    Groq   : 추론을 숨기므로 바이트는 그대로고 패킷 사이 간격만 벌어진다.
  즉 '어떤 피처가 신호를 싣는가'가 provider 별로 다르다는 뜻이고,
  6개만으로는 그 차이를 충분히 포착하지 못한다. 분포 모양·구간별 변화·순서열까지 넓게 뽑아
  뒤에서 피처 선택으로 좁히는 편이 낫다.

뽑는 피처 묶음:
  (1) 방향(up/down/all) x 대상(패킷 크기, 패킷 간격) x 통계량(개수·합·평균·중앙·표준편차·
      최소·최대·분위수 10/25/75/90·변동계수·왜도)  → 약 70개
  (2) 요청 구간을 시간으로 4등분한 구간별 하향 패킷수·바이트·간격평균  → 12개
      (추론이 앞쪽에 몰리는지 뒤쪽인지는 전체 평균으로는 안 보인다)
  (3) 앞 N개 패킷의 크기(방향을 부호로)와 도착 간격 순서열  → 2N개 (기본 N=20)
      (순서 정보를 처음으로 쓰는 피처. 고정 길이로 펴서 트리에도 넣을 수 있다)
  (4) 파생 비율 — 질문마다 기준선이 다른 문제를 비율로 완화해 보려는 것  → 약 10개

호환:
  기존 parse_pcap.py 가 내던 열 이름을 모두 그대로 유지하므로 e1_from_csv.py 등이 바로 돈다.

사용:
  python3 parse_pcap_rich.py <pcap> <log.jsonl> --local-ip 163.152.223.17 --out out/gem_rich.csv
작성일: 2026-10-05
"""
import sys
import csv
import json
import math
import socket
import argparse
import statistics as st
from pathlib import Path

from scapy.all import rdpcap, IP, TCP

BUFFER_S = 1.0      # 요청 t_end 이후 여유(응답 꼬리 패킷 포함)
HEAD_N = 20         # 앞 N개 패킷 순서열 길이
NBIN = 4            # 요청 구간 분할 수


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def pct(sorted_vals, p):
    """정렬된 리스트의 p 분위수(0~1). 선형보간."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    i = (len(sorted_vals) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def dist_stats(vals, prefix, with_count=True):
    """한 수열의 분포를 여러 통계량으로 펼친다.

    평균만으로는 '고르게 퍼졌는지 한쪽에 몰렸는지'를 구분할 수 없어
    분위수·변동계수·왜도까지 함께 뽑는다.
    """
    d = {}
    v = sorted(x for x in vals if x is not None)
    n = len(v)
    if with_count:
        d[f"{prefix}_n"] = n
        d[f"{prefix}_sum"] = round(sum(v), 1) if n else None
    if n == 0:
        for k in ["mean", "median", "std", "min", "max", "p10", "p25", "p75", "p90", "cv", "skew"]:
            d[f"{prefix}_{k}"] = None
        return d
    m = sum(v) / n
    sd = st.pstdev(v) if n > 1 else 0.0
    d[f"{prefix}_mean"] = round(m, 2)
    d[f"{prefix}_median"] = round(st.median(v), 2)
    d[f"{prefix}_std"] = round(sd, 2)
    d[f"{prefix}_min"] = round(v[0], 2)
    d[f"{prefix}_max"] = round(v[-1], 2)
    for p, name in [(0.10, "p10"), (0.25, "p25"), (0.75, "p75"), (0.90, "p90")]:
        d[f"{prefix}_{name}"] = round(pct(v, p), 2)
    # 변동계수 = 표준편차/평균. 단위를 없애 질문 간 비교가 조금 쉬워진다.
    d[f"{prefix}_cv"] = round(sd / m, 3) if m else None
    # 왜도: 한쪽 꼬리가 긴지. 추론이 폭주한 콜이 섞이면 커진다.
    d[f"{prefix}_skew"] = round(sum((x - m) ** 3 for x in v) / (n * sd ** 3), 3) if sd > 0 else 0.0
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap")
    ap.add_argument("log")
    ap.add_argument("--local-ip", default=None,
                    help="캡처 당시 클라이언트 IP. 다른 머신 pcap 파싱시 필수.")
    ap.add_argument("--out", default="out/packet_features_rich.csv")
    ap.add_argument("--head-n", type=int, default=HEAD_N, help="앞 N패킷 순서열 길이")
    a = ap.parse_args()
    LOCAL = a.local_ip or local_ip()
    print(f"local IP = {LOCAL}" + ("  (override)" if a.local_ip else "  (자동감지)"))

    entries = []
    with open(a.log, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("error") or not e.get("t_start"):
                continue
            entries.append(e)
    print(f"요청 {len(entries)}개")

    print("pcap 읽는 중...")
    recs = []
    for p in rdpcap(a.pcap):
        if IP in p and TCP in p:
            recs.append((float(p.time), p[IP].src, p[IP].dst, len(p[TCP].payload)))
    recs.sort()
    print(f"패킷 {len(recs)}개")

    rows = []
    for e in entries:
        t0 = e["t_start"]
        t1 = (e.get("t_end") or e["t_start"]) + BUFFER_S
        win = [r for r in recs if t0 <= r[0] <= t1]
        out = [r for r in win if r[1] == LOCAL and r[3] > 0]    # client -> server
        inc = [r for r in win if r[2] == LOCAL and r[3] > 0]    # server -> client
        allp = sorted(out + inc)

        t_req = out[0][0] if out else None
        t_resp = None
        if t_req is not None:
            later = [r for r in inc if r[0] >= t_req]
            t_resp = later[0][0] if later else None
        pkt_gap_ms = round((t_resp - t_req) * 1000, 1) if (t_req and t_resp) else None

        up_sizes = [r[3] for r in out]
        down_sizes = [r[3] for r in inc]
        all_sizes = [r[3] for r in allp]

        def iats_of(lst):
            ts = sorted(r[0] for r in lst)
            return [(ts[i + 1] - ts[i]) * 1000 for i in range(len(ts) - 1)]
        up_iats, down_iats, all_iats = iats_of(out), iats_of(inc), iats_of(allp)

        # --- 기존 parse_pcap.py 와 같은 열 이름 유지(하위 호환) ---
        row = {
            "idx": e["idx"], "q_idx": e["q_idx"], "condition": e["condition"], "rep": e["rep"],
            "pkt_gap_ms": pkt_gap_ms,
            "up_pkts": len(out), "down_pkts": len(inc),
            "up_bytes": sum(up_sizes), "down_bytes": sum(down_sizes),
            "down_pkt_mean": round(st.mean(down_sizes), 1) if down_sizes else None,
            "down_pkt_max": max(down_sizes) if down_sizes else None,
            "down_iat_mean_ms": round(st.mean(down_iats), 1) if down_iats else None,
            "n_pkts_window": len(win),
            "app_ttft_ms": e.get("app_ttft_ms"),
            "thoughts_tokens": e.get("thoughts_tokens"),
            "answer_chars": e.get("answer_chars"),
            "truncated": 1 if e.get("truncated") else 0,
            "output_tokens": e.get("output_tokens"),
        }

        # --- (1) 방향 x 대상 x 통계량 ---
        row.update(dist_stats(up_sizes, "upsz"))
        row.update(dist_stats(down_sizes, "dnsz"))
        row.update(dist_stats(all_sizes, "allsz"))
        row.update(dist_stats(up_iats, "upiat", with_count=False))
        row.update(dist_stats(down_iats, "dniat", with_count=False))
        row.update(dist_stats(all_iats, "alliat", with_count=False))

        # --- (2) 요청 구간 4등분: 추론이 앞쪽에 몰리는지 뒤쪽인지 ---
        span = (t1 - BUFFER_S) - t0
        for b in range(NBIN):
            lo = t0 + span * b / NBIN
            hi = t0 + span * (b + 1) / NBIN
            seg = [r for r in inc if lo <= r[0] < hi]
            st_ = sorted(r[0] for r in seg)
            sg_iat = [(st_[i + 1] - st_[i]) * 1000 for i in range(len(st_) - 1)]
            row[f"bin{b}_dn_pkts"] = len(seg)
            row[f"bin{b}_dn_bytes"] = sum(r[3] for r in seg)
            row[f"bin{b}_dn_iat_mean"] = round(st.mean(sg_iat), 2) if sg_iat else None

        # --- (3) 앞 N패킷 순서열: 크기(상향 +, 하향 -)와 도착 간격 ---
        base = allp[0][0] if allp else None
        prev = base
        for i in range(a.head_n):
            if i < len(allp):
                t, src, _dst, ln = allp[i]
                row[f"h{i}_size"] = ln if src == LOCAL else -ln
                row[f"h{i}_dt"] = round((t - prev) * 1000, 2)
                prev = t
            else:
                row[f"h{i}_size"] = 0        # 패킷이 그만큼 없으면 0으로 메움
                row[f"h{i}_dt"] = 0

        # --- (4) 파생 비율: 질문별 기준선 차이를 비율로 완화해 보려는 시도 ---
        ub, db = sum(up_sizes), sum(down_sizes)
        total_ms = (allp[-1][0] - allp[0][0]) * 1000 if len(allp) > 1 else None
        row["ratio_dn_up_bytes"] = round(db / ub, 3) if ub else None
        row["bytes_per_dn_pkt"] = round(db / len(inc), 1) if inc else None
        row["gap_over_total"] = round(pkt_gap_ms / total_ms, 3) if (pkt_gap_ms and total_ms) else None
        row["total_ms"] = round(total_ms, 1) if total_ms else None
        mi = st.mean(down_iats) if down_iats else None
        row["maxiat_over_mean"] = round(max(down_iats) / mi, 2) if (down_iats and mi) else None
        # 평균 간격의 2배를 넘는 '멈춤'의 횟수와 총 길이 — 은닉 추론이 남기는 흔적 후보
        if down_iats and mi:
            stalls = [x for x in down_iats if x > 2 * mi]
            row["n_stalls"] = len(stalls)
            row["stall_total_ms"] = round(sum(stalls), 1)
            row["stall_ratio"] = round(sum(stalls) / sum(down_iats), 3) if sum(down_iats) else None
        else:
            row["n_stalls"] = row["stall_total_ms"] = row["stall_ratio"] = None
        row["dn_over_all_pkts"] = round(len(inc) / len(allp), 3) if allp else None
        row["first_dn_frac"] = round(down_sizes[0] / db, 3) if (down_sizes and db) else None
        row["last_dn_frac"] = round(down_sizes[-1] / db, 3) if (down_sizes and db) else None

        rows.append(row)

    cols = list(rows[0].keys()) if rows else []
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    feat_cols = [c for c in cols if c not in
                 ("idx", "q_idx", "condition", "rep", "app_ttft_ms",
                  "thoughts_tokens", "output_tokens")]
    print(f"\n[out] {outp}  ({len(rows)}행, 피처 {len(feat_cols)}개)")
    print("→ 다음: python3 feature_select.py <label>=" + str(outp))


if __name__ == "__main__":
    main()
