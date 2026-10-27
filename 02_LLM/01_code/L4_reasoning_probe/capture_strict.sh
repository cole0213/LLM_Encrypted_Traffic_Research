#!/usr/bin/env bash
# capture_strict.sh — 길이 완전통제판(Gemini): tcpdump로 패킷 캡처하며
#   A/B/C/D 단답 강제 요청을 생성한다(capture_run_strict.py). capture.sh 의 strict 짝.
#
# capture.sh 와의 차이: capture.sh 는 옛 capture_run.py(자유 응답, 길이통제 없음)를 부른다.
#   같은 이름의 pcap/로그를 쓰면 옛 데이터와 섞이므로 파일명도 strict 로 분리했다.
#
# 사용: bash capture_strict.sh <tag> [python args...]
#   예) bash capture_strict.sh day2 --repeats 5
#       bash capture_strict.sh day2 --repeats 5 --seed 7     # 다른 순서로 다시
# 출력: out/gem_strict_<tag>_<ts>.pcap , out/gem_strict_<tag>_log.jsonl
# 파싱: python3 parse_pcap.py out/gem_strict_<tag>_<ts>.pcap out/gem_strict_<tag>_log.jsonl \
#        --local-ip 163.152.223.17 --out out/gem_strict2.csv
# 작성일: 2026-10-02
set -e
cd "$(dirname "$0")"; mkdir -p out
TAG="${1:-run}"; shift || true
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/gem_strict_${TAG}_${TS}.pcap"; LOG="out/gem_strict_${TAG}_log.jsonl"
HOST="generativelanguage.googleapis.com"
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
python3 capture_run_strict.py --log "$LOG" "$@" || true
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17 --out out/gem_strict2.csv"
