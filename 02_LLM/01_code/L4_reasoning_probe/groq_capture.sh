#!/usr/bin/env bash
# groq_capture.sh — E3: tcpdump로 Groq(api.groq.com) 패킷 캡처하며 요청 생성.
# 사용: bash groq_capture.sh <tag> [python args...]
#   예) bash groq_capture.sh 20b  --repeats 3
#       bash groq_capture.sh 120b --model openai/gpt-oss-120b --repeats 3
# 출력: out/groq_<tag>_<ts>.pcap , out/groq_<tag>_log.jsonl
# 작성일: 2026-09-02
set -e
cd "$(dirname "$0")"; mkdir -p out
TAG="${1:-run}"; shift || true
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/groq_${TAG}_${TS}.pcap"; LOG="out/groq_${TAG}_log.jsonl"
HOST="api.groq.com"
IPS=$(getent ahostsv4 "$HOST" 2>/dev/null | awk '{print $1}' | sort -u)
if [ -n "$IPS" ]; then
  FILTER="tcp port 443 and ("; first=1
  for ip in $IPS; do
    if [ $first -eq 1 ]; then FILTER="$FILTER host $ip"; first=0; else FILTER="$FILTER or host $ip"; fi
  done
  FILTER="$FILTER)"
else FILTER="tcp port 443"; fi
echo "필터: $FILTER"; echo "pcap: $PCAP  log: $LOG"
tcpdump -i any -U -w "$PCAP" $FILTER >/dev/null 2>&1 &
TPID=$!; echo "tcpdump PID=$TPID, 2초 워밍업..."; sleep 2
python3 groq_capture_run.py --log "$LOG" "$@" || true
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17"
