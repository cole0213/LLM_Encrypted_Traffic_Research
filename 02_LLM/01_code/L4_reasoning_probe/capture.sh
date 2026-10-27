#!/usr/bin/env bash
# capture.sh — Phase 1: tcpdump로 패킷 캡처하며 Gemini 요청을 동기 실행.
# 목적: 실제 네트워크 패킷(pcap)과 요청 로그를 한 번에 수집.
# 사용: bash capture.sh [--limit N] [--repeats R]
#   (root 권장. tcpdump 필요: apt install tcpdump)
# 출력: out/capture_<ts>.pcap , out/capture_log.jsonl
# 작성일: 2026-09-01
set -e
cd "$(dirname "$0")"
mkdir -p out
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/capture_${TS}.pcap"

# Gemini API 호스트 IP 확인(필터용). 여러 IP일 수 있어 실패시 port 443 전체 캡처로 폴백.
HOST="generativelanguage.googleapis.com"
IPS=$(getent ahostsv4 "$HOST" 2>/dev/null | awk '{print $1}' | sort -u)
if [ -n "$IPS" ]; then
  FILTER="tcp port 443 and ("
  first=1
  for ip in $IPS; do
    if [ $first -eq 1 ]; then FILTER="$FILTER host $ip"; first=0; else FILTER="$FILTER or host $ip"; fi
  done
  FILTER="$FILTER)"
else
  FILTER="tcp port 443"
fi
echo "필터: $FILTER"
echo "pcap:  $PCAP"

# tcpdump 백그라운드 시작(-i any = 모든 인터페이스). -U=즉시flush.
tcpdump -i any -U -w "$PCAP" $FILTER >/dev/null 2>&1 &
TPID=$!
echo "tcpdump PID=$TPID, 2초 워밍업..."
sleep 2

# 요청 실행(로그 남김). 인자 그대로 전달.
python3 capture_run.py --log out/capture_log.jsonl "$@" || true

sleep 2
echo "tcpdump 종료..."
kill $TPID 2>/dev/null || true
wait $TPID 2>/dev/null || true

echo
echo "완료. 다음:  python3 parse_pcap.py $PCAP out/capture_log.jsonl"
echo "  (pcap: $PCAP)"
