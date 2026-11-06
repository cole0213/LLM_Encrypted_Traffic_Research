#!/usr/bin/env bash
# openai_capture_strict.sh — 길이 완전통제판(OpenAI): tcpdump 로 패킷을 캡처하며
#   A/B/C/D 단답 강제 요청을 생성한다(openai_capture_run_strict.py).
#   groq_capture_strict.sh 의 OpenAI 짝. 필터 호스트만 다르고 절차는 같다.
#
# 사용: bash openai_capture_strict.sh <tag> [python args...]
#   예) bash openai_capture_strict.sh base --model gpt-5-mini --repeats 3
#       bash openai_capture_strict.sh len  --model gpt-5-mini --arms free_brief
#   ※ arm 은 반드시 따로 캡처할 것. 한 캡처에 섞으면 거대 응답이 다음 콜의
#      측정창을 오염시킨다(HANDOFF 3-13(b)).
# 출력: out/openai_strict_<tag>_<ts>.pcap , out/openai_strict_<tag>_log.jsonl
# 파싱: python3 parse_pcap.py out/openai_strict_<tag>_<ts>.pcap out/openai_strict_<tag>_log.jsonl \
#        --local-ip 163.152.223.17 --out out/openai_<tag>.csv
# 작성일: 2026-11-06
set -e
cd "$(dirname "$0")"; mkdir -p out
TAG="${1:-run}"; shift || true
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/openai_strict_${TAG}_${TS}.pcap"; LOG="out/openai_strict_${TAG}_log.jsonl"
HOST="api.openai.com"
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
python3 openai_capture_run_strict.py --log "$LOG" "$@" || true
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17 --out out/openai_${TAG}.csv"
