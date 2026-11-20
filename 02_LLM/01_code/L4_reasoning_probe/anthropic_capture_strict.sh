#!/usr/bin/env bash
# anthropic_capture_strict.sh — 길이 완전통제판(Anthropic): tcpdump 로 패킷을 캡처하며
#   A/B/C/D 단답 강제 요청을 생성한다(anthropic_capture_run_strict.py).
#   openai_capture_strict.sh 의 Claude 짝. 필터 호스트만 다르고 절차는 같다.
#
# 사용: bash anthropic_capture_strict.sh <tag> [python args...]
#   예) bash anthropic_capture_strict.sh wiretest --model claude-haiku-5-5 \
#         --qset v2 --qfile out/qfile_gemini481.json \
#         --efforts low,medium,high,xhigh,max --limit 3 --repeats 1 --sleep 3
# 출력: out/anthropic_strict_<tag>_<ts>.pcap , out/anthropic_strict_<tag>_log.jsonl
# 파싱: python3 parse_pcap.py out/anthropic_strict_<tag>_<ts>.pcap \
#        out/anthropic_strict_<tag>_log.jsonl --local-ip 163.152.223.17 \
#        --out out/anthropic_<tag>.csv
# 작성일: 2026-11-17
set -e
cd "$(dirname "$0")"; mkdir -p out
TAG="${1:-run}"; shift || true
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/anthropic_strict_${TAG}_${TS}.pcap"; LOG="out/anthropic_strict_${TAG}_log.jsonl"
# 캡처할 호스트. 게이트웨이를 쓸 때는 반드시 같이 바꿔야 한다 —
# 필터가 틀리면 tcpdump 가 엉뚱한 트래픽을 잡고 pcap 에 우리 콜이 한 패킷도 없다.
HOST="${CAPTURE_HOST:-api.anthropic.com}"
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
# -u : 출력 버퍼링을 끈다. nohup 으로 파일에 리다이렉트하면 블록 버퍼링이 되어
#      4KB 가 찰 때까지 진행 상황이 한 줄도 안 보인다.
python3 -u anthropic_capture_run_strict.py --log "$LOG" "$@" || RC=$?
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
if [ "$RC" -ne 0 ]; then
  echo; echo "[실패] anthropic_capture_run_strict.py 가 종료코드 $RC 로 끝났다. 캡처는 쓸 수 없다."
  echo "       로그 마지막 줄을 확인하라: $LOG"
  exit "$RC"
fi
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17 --out out/anthropic_${TAG}.csv"
