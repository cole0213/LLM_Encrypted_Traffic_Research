"""
parse_pcap.py — pcap을 요청 구간별로 잘라 패킷 피처 추출 + 라벨링.

목적: capture.sh가 만든 pcap과 로그를 맞춰, 각 요청(조건 라벨 있음) 구간의
      패킷 레벨 피처를 뽑는다. 핵심 = pkt_gap_ms(첫 요청패킷 → 첫 응답패킷 간격)
      = 앱타이밍 ttft의 패킷 버전. 이게 조건별로 갈리면 "네트워크 패킷으로도
      추론 신호가 보인다" = Phase 1 성공.

사용: python3 parse_pcap.py <pcap> <capture_log.jsonl>
입력: pcap, JSONL 로그(요청별 t_start/t_end/condition).
출력: out/packet_features.csv (요청별 패킷 피처 + 라벨)
비고: TLS 복호화 안 함(패킷 크기·방향·타이밍만 = SNI-free 정신).
작성일: 2026-09-01
"""
import sys
import csv
import json
import socket
import statistics as st
from pathlib import Path

from scapy.all import rdpcap, IP, TCP

BUFFER_S = 1.0   # 요청 t_end 이후 여유(응답 꼬리 패킷 포함)


def local_ip():
    """이 머신의 로컬 IP(방향 판별용)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _flag(v):
    """불린/빈값 → CSV 용 1/0/빈칸. 옛 로그에 열이 없으면 빈칸으로 남긴다."""
    return "" if v is None else (1 if v else 0)


def _token_cols(e):
    """'답 길이' 토큰 수와, usage 숫자 자릿수 통제변수를 만든다.

    왜 필요한가 — provider 마다 output_tokens 의 의미가 다르다.
      * Gemini candidates_token_count : 답만 센다. 그대로 쓰면 된다.
      * Groq  completion_tokens       : **추론 토큰을 포함**한다.
        실측상 completion - reasoning = 10 이 예외 없이 고정(3차 20b 267/270, 120b 270/270.
        어긋난 3건은 전부 토큰한계로 잘린 q4). 즉 이 값을 '길이'라고 부르면
        사실상 정답 라벨을 보는 것이라, length-only 대조가 0.966 까지 올라가
        "길이를 통제했다"는 주장과 정면으로 모순된다.
      → answer_tokens 를 따로 만들어 length-only 대조는 이쪽을 쓴다.

    tok_digits 는 응답 JSON 안 usage 숫자들의 자릿수 합(근사).
    답을 한 글자로 고정해도 이 자릿수가 늘면 암호문 바이트가 그만큼 늘어나,
    down_bytes 에 추론량과 상관된 가짜 신호가 생긴다(Groq 3차에서 AUC 0.85~0.91이
    전부 이 경로였다 — 자릿수를 고정하면 신호가 0으로 사라진다).
    """
    ot = e.get("output_tokens")
    th = e.get("thoughts_tokens")
    # service 키가 없는 옛 Gemini 로그는 기본값으로 처리된다.
    is_groq = e.get("service") == "groq"
    ans_tok = (ot - (th or 0)) if (is_groq and ot is not None) else ot
    digits = sum(len(str(v)) for v in (ot, th) if v is not None)
    return {"answer_tokens": ans_tok, "tok_digits": digits or None}


def main():
    # --local-ip: 다른 머신에서 뜬 pcap을 파싱할 때 필수(캡처 당시 클라이언트 IP).
    # 미지정시 이 머신 IP 자동감지 → 캡처 머신과 다르면 방향판별 실패로 전부 0이 됨.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap")
    ap.add_argument("log")
    ap.add_argument("--local-ip", default=None,
                    help="캡처 당시 클라이언트 IP. 다른 머신 pcap 파싱시 필수.")
    ap.add_argument("--out", default="out/packet_features.csv",
                    help="출력 CSV 경로(서비스별 분리 저장용).")
    a = ap.parse_args()
    pcap_path, log_path = a.pcap, a.log
    LOCAL = a.local_ip or local_ip()
    print(f"local IP = {LOCAL}" + ("  (override)" if a.local_ip else "  (자동감지)"))

    # 로그(요청 구간) 로드.
    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("error") or not e.get("t_start"):
                continue
            entries.append(e)
    print(f"요청 {len(entries)}개")

    # pcap → (time, src, dst, payload_len) 목록.
    print("pcap 읽는 중...")
    pkts = rdpcap(pcap_path)
    recs = []
    for p in pkts:
        if IP in p and TCP in p:
            plen = len(p[TCP].payload)   # TCP 데이터 바이트(ACK=0)
            recs.append((float(p.time), p[IP].src, p[IP].dst, plen))
    recs.sort()
    print(f"패킷 {len(recs)}개")

    rows = []
    for e in entries:
        t0 = e["t_start"]
        t1 = (e.get("t_end") or e["t_start"]) + BUFFER_S
        win = [r for r in recs if t0 <= r[0] <= t1]
        out = [r for r in win if r[1] == LOCAL and r[3] > 0]   # client→server 데이터
        inc = [r for r in win if r[2] == LOCAL and r[3] > 0]   # server→client 데이터

        t_req = out[0][0] if out else None            # 첫 요청 데이터 패킷
        t_resp = None
        if t_req is not None:
            later = [r for r in inc if r[0] >= t_req]
            t_resp = later[0][0] if later else None
        pkt_gap_ms = round((t_resp - t_req) * 1000, 1) if (t_req and t_resp) else None

        up_bytes = sum(r[3] for r in out)
        down_bytes = sum(r[3] for r in inc)
        down_sizes = [r[3] for r in inc]
        # server→client 패킷 간 간격(IAT) 통계.
        down_times = sorted(r[0] for r in inc)
        iats = [(down_times[i+1]-down_times[i])*1000 for i in range(len(down_times)-1)]
        rows.append({
            "idx": e["idx"], "q_idx": e["q_idx"], "condition": e["condition"],
            "rep": e["rep"],
            "pkt_gap_ms": pkt_gap_ms,                 # ★ 요청→첫응답 패킷 간격
            "up_pkts": len(out), "down_pkts": len(inc),
            "up_bytes": up_bytes, "down_bytes": down_bytes,
            "down_pkt_mean": round(st.mean(down_sizes), 1) if down_sizes else None,
            "down_pkt_max": max(down_sizes) if down_sizes else None,
            "down_iat_mean_ms": round(st.mean(iats), 1) if iats else None,
            "n_pkts_window": len(win),
            # 참고로 앱지표도 같이(비교용).
            "app_ttft_ms": e.get("app_ttft_ms"),
            "thoughts_tokens": e.get("thoughts_tokens"),
            "answer_chars": e.get("answer_chars"),
            "truncated": 1 if e.get("truncated") else 0,
            "output_tokens": e.get("output_tokens"),
            **_token_cols(e),
            # 추론 텍스트가 실제로 내려왔는지(캡처 스크립트가 기록한 경우만 채워짐).
            # down_bytes 가 '은닉 추론의 사이드채널'인지 '그냥 추론 요약이 전송된 것'인지
            # 가르는 열이다. 옛 로그에는 없으므로 빈칸이 정상.
            "thought_chars": e.get("thought_chars", e.get("reasoning_chars")),
            "had_thought": _flag(e.get("had_thought", e.get("had_reasoning"))),
            "chunk_count": e.get("chunk_count"),
        })

    out_csv = Path(a.out)
    cols = list(rows[0].keys()) if rows else []
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # 조건별 pkt_gap 중앙값 요약(핵심 확인).
    print("\n=== 조건별 패킷 간격(pkt_gap_ms) vs 앱(ttft) ===")
    print(f"{'condition':11s} {'n':>3s} {'pkt_gap중앙':>10s} {'app_ttft중앙':>11s} "
          f"{'down_bytes중앙':>13s} {'answer_tok':>10s}")
    # 조건을 하드코딩하면 Groq gpt-oss 의 think_med 가 요약에서 통째로 빠져 "데이터 없나?"로
    # 오해하게 된다. 실제 데이터에 있는 조건을 쓰되, 얕은→깊은 순서는 고정한다.
    order = ["no_think", "think_low", "think_med", "think_high"]
    present = [c for c in order if any(r["condition"] == c for r in rows)]
    present += sorted({r["condition"] for r in rows} - set(order))
    for c in present:
        sub = [r for r in rows if r["condition"] == c]
        def med(k):
            vs = [r[k] for r in sub if r[k] is not None]
            return round(st.median(vs), 1) if vs else None
        # answer_tok 이 조건마다 같은 값이면 '답 길이 고정'이 토큰 수준에서 지켜진 것.
        print(f"{c:11s} {len(sub):>3d} {str(med('pkt_gap_ms')):>10s} "
              f"{str(med('app_ttft_ms')):>11s} {str(med('down_bytes')):>13s} "
              f"{str(med('answer_tokens')):>10s}")
    print(f"\n[out] {out_csv}  ({len(rows)}행)")
    print("→ think_high의 pkt_gap이  얕은 조건보다 크면 = 패킷 레벨서도 추론 신호 확인!")
    print("→ answer_tok 이 조건 간 동일하면 = 출력 길이 통제가 토큰 수준에서 성립.")


if __name__ == "__main__":
    main()
