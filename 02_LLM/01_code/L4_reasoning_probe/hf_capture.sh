#!/usr/bin/env bash
# hf_capture.sh — 인프라 격리: tcpdump로 router.huggingface.co 패킷 캡처하며 요청 생성.
# 사용: bash hf_capture.sh <tag> [python args...]
#   예) bash hf_capture.sh fw  --repeats 5                       # 기본 fireworks-ai(느린 GPU)
#       bash hf_capture.sh tg  --provider together --repeats 5
# 출력: out/hf_<tag>_<ts>.pcap , out/hf_<tag>_log.jsonl
# 준비: export HF_TOKEN=hf_...   (https://huggingface.co/settings/tokens, 카드 X)
# 작성일: 2026-09-05
set -e
cd "$(dirname "$0")"; mkdir -p out
TAG="${1:-run}"; shift || true
TS=$(date +%Y%m%d_%H%M%S)
PCAP="out/hf_${TAG}_${TS}.pcap"; LOG="out/hf_${TAG}_log.jsonl"
# HOST 환경변수로 tcpdump 필터 대상 교체(Nebius=api.tokenfactory.nebius.com 등). 기본 HF.
HOST="${HOST:-router.huggingface.co}"
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
python3 hf_capture_run.py --log "$LOG" "$@" || true
sleep 2; kill $TPID 2>/dev/null || true; wait $TPID 2>/dev/null || true
echo; echo "완료. 다음:  python3 parse_pcap.py $PCAP $LOG --local-ip <서버IP> --out out/hf_${TAG}_feats.csv"
