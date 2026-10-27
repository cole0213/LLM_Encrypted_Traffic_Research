#!/usr/bin/env bash
# sweep_arm.sh — 응답 길이 arm 선행 실험(E4 파일럿). tcpdump와 함께 길이 쓸기 1회 수행.
#
# 왜 하는가: 지금까지의 결과는 전부 '답 1글자' 조건이라 탐지 성능이 아니라 상한(best case)이다.
#   실제 응답 길이에서 추론 신호가 스트림에 묻히는지는 측정한 적이 없다. 본실험의 S/M/L 길이를
#   추측으로 정하지 말고, 먼저 넓게 쓸어서 (1) 지시 준수율 (2) 콜당 소요시간 (3) 토큰 소모
#   (4) 신호가 꺾이는 지점을 실측한 뒤 그에 맞춰 본실험 길이를 정한다.
#
# 사용: bash sweep_arm.sh <provider> <tag> [python args...]
#   provider = gem | groq
#   예) bash sweep_arm.sh groq sweep1 --model openai/gpt-oss-120b
#       bash sweep_arm.sh gem  sweep1
# 기본 규모: 8문항 x 3조건 x 5arm x 1반복 = 120콜
# 출력: out/<provider>_sweep_<tag>_<ts>.pcap , out/<provider>_sweep_<tag>_log.jsonl
# 작성일: 2026-10-27
set -e
cd "$(dirname "$0")"; mkdir -p out

PROV="${1:?provider 필요 (gem|groq)}"; TAG="${2:-sweep}"; shift 2 || true
TS=$(date +%Y%m%d_%H%M%S)

case "$PROV" in
  gem)
    HOST="generativelanguage.googleapis.com"
    RUNNER="capture_run_strict.py"
    ;;
  groq)
    HOST="api.groq.com"
    RUNNER="groq_capture_run_strict.py"
    ;;
  *) echo "provider 는 gem 또는 groq"; exit 1 ;;
esac

PCAP="out/${PROV}_sweep_${TAG}_${TS}.pcap"
LOG="out/${PROV}_sweep_${TAG}_log.jsonl"

# 길이 쓸기 범위. 0 = 기존 1글자 프로토콜(3차와 직접 비교 가능한 기준선).
# free_* 는 길이를 통제하지 않는 자유 응답 — 실제로 몇 토큰이 나오는지 재는 쪽이다.
# 본실험의 고정 길이를 추측으로 정하지 않고 이 분포에 맞춰 잡는다.
ARMS="0,400,1600,free_brief,free_full"
# 문항은 앞 8개만. 파일럿 목적은 정확도 확정이 아니라 경계 탐색이다.
LIMIT=8
REPEATS=1

# 캡처 필터를 대상 호스트 IP로 좁힘(무관 트래픽 배제). 해석 실패 시 443 전체.
IPS=$(getent ahostsv4 "$HOST" 2>/dev/null | awk '{print $1}' | sort -u)
if [ -n "$IPS" ]; then
  FILTER="tcp port 443 and ("; first=1
  for ip in $IPS; do
    if [ $first -eq 1 ]; then FILTER="$FILTER host $ip"; first=0; else FILTER="$FILTER or host $ip"; fi
  done
  FILTER="$FILTER)"
else FILTER="tcp port 443"; fi

echo "provider: $PROV   arms: $ARMS   문항 $LIMIT x 3조건 x 5arm x $REPEATS반복 = $((LIMIT*3*5*REPEATS))콜"
echo "필터: $FILTER"
echo "pcap: $PCAP"
echo "log : $LOG"

tcpdump -i any -U -w "$PCAP" $FILTER >/dev/null 2>&1 &
TPID=$!; echo "tcpdump PID=$TPID, 2초 워밍업..."; sleep 2

python3 "$RUNNER" --log "$LOG" --arms "$ARMS" --limit "$LIMIT" --repeats "$REPEATS" "$@" || true

sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true

echo
echo "완료. 다음:"
echo "  python3 parse_pcap.py $PCAP $LOG --local-ip 163.152.223.17 --out out/${PROV}_sweep_${TAG}.csv"
echo
echo "확인할 것:"
echo "  1) arm 별 [불일치] 건수 — 준수율 80% 밑인 arm 은 본실험서 제외"
echo "  2) arm 별 [잘림] 건수 — max_completion/output_tokens 를 더 올려야 하는지"
echo "  3) 총 소요시간 — 본실험(문항x3조건x3armx2반복) 시간 추정의 근거"
echo "  4) arm 별 think 토큰 분포가 이동하는지 — 이동하면 길이가 추론량 자체를 바꾼 것(교란)"
