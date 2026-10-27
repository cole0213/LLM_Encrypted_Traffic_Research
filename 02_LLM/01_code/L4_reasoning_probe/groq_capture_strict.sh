#!/usr/bin/env bash
# groq_capture_strict.sh — 길이 완전통제판(Groq): tcpdump로 api.groq.com 패킷 캡처하며
#   A/B/C/D 단답 강제 요청 생성(groq_capture_run_strict.py). groq_capture.sh의 strict 짝.
# 사용: bash groq_capture_strict.sh <tag> [python args...]
#   예) bash groq_capture_strict.sh 20b  --repeats 3
#       bash groq_capture_strict.sh 120b --model openai/gpt-oss-120b --repeats 3
# 출력: out/groq_strict_<tag>_<ts>.pcap , out/groq_strict_<tag>_log.jsonl
# 파싱: python3 parse_pcap.py out/groq_strict_<tag>_<ts>.pcap out/groq_strict_<tag>_log.jsonl \
#        --local-ip 163.152.223.17 --out out/groq_strict.csv
# 작성일: 2026-09-23
set -e
cd "$(dirname "$0")"; mkdir -p out
TAG="${1:-run}"; shift || true
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/groq_strict_${TAG}_${TS}.pcap"; LOG="out/groq_strict_${TAG}_log.jsonl"
HOST="api.groq.com"
# 캡처 필터를 대상 호스트 IP로 좁힘(무관 트래픽 배제). 해석 실패 시 443 전체.
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
python3 groq_capture_run_strict.py --log "$LOG" "$@" || true
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17 --out out/groq_strict.csv"
