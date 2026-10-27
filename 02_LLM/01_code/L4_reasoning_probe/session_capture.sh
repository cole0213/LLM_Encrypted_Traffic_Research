#!/usr/bin/env bash
# session_capture.sh — L5: tcpdump로 패킷 캡처하며 human/agent 세션 생성.
# 사용: bash session_capture.sh [--sessions N]
# 출력: out/session_<ts>.pcap , out/session_log.jsonl
# 작성일: 2026-09-02
set -e
cd "$(dirname "$0")"
mkdir -p out
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/session_${TS}.pcap"
HOST="generativelanguage.googleapis.com"
IPS=$(getent ahostsv4 "$HOST" 2>/dev/null | awk '{print $1}' | sort -u)
if [ -n "$IPS" ]; then
  FILTER="tcp port 443 and ("; first=1
  for ip in $IPS; do
    if [ $first -eq 1 ]; then FILTER="$FILTER host $ip"; first=0; else FILTER="$FILTER or host $ip"; fi
  done
  FILTER="$FILTER)"
else FILTER="tcp port 443"; fi
echo "필터: $FILTER"; echo "pcap: $PCAP"
tcpdump -i any -U -w "$PCAP" $FILTER >/dev/null 2>&1 &
TPID=$!; echo "tcpdump PID=$TPID, 2초 워밍업..."; sleep 2
python3 session_run.py --log out/session_log.jsonl "$@" || true
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
echo; echo "완료. 다음:  python3 session_classify.py $PCAP out/session_log.jsonl"
