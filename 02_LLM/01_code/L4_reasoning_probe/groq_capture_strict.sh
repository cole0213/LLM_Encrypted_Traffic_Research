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
# 종료 코드를 받아둔다. '|| true' 가 필요한 이유: set -e 로 여기서 죽으면
# 아래 kill 이 안 돌아 tcpdump 가 좀비로 남는다. 다만 실패를 삼키면 안 된다 —
# 키가 없어 파이썬이 즉시 죽어도 "완료" 가 찍혀서, 밤새 돌린 줄 알고 아침에야 안다.
RC=0
# -u : 출력 버퍼링을 끈다. nohup 으로 파일에 리다이렉트하면 파이썬이 블록 버퍼링으로
#      바뀌어, 4KB 가 찰 때까지 진행 상황이 한 줄도 안 보인다. 밤새 돌리는 작업에서
#      '돌고 있는지'와 '죽었는지'가 구분되지 않는다.
python3 -u groq_capture_run_strict.py --log "$LOG" "$@" || RC=$?
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
if [ "$RC" -ne 0 ]; then
  echo; echo "[실패] groq_capture_run_strict.py 가 종료코드 $RC 로 끝났다. 캡처는 쓸 수 없다."
  echo "       로그 마지막 줄을 확인하라: $LOG"
  exit "$RC"
fi
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17 --out out/groq_strict.csv"
