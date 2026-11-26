#!/usr/bin/env bash
# run_openai_rest.sh — 지금 돌고 있는 S5 가 끝나기를 기다렸다가,
#   OpenAI 크레딧 만료(2026-11-23) 전에 남은 잔액으로 돌릴 수 있는 단계를
#   가치 순으로 이어서 돌린다.
#
# 왜 기다리는가
#   캡처는 반드시 직렬이어야 한다. 두 캡처가 겹치면 서로의 측정창에 패킷이 섞여
#   타이밍 피처(ttft·iat·stall)가 통째로 망가진다. 그래서 러너 프로세스가
#   완전히 사라질 때까지 60초 간격으로 기다린 뒤에만 다음 단계를 띄운다.
#
# 왜 BUDGET 을 직접 안 적는가
#   S5 가 얼마를 쓸지는 끝나봐야 안다(투영 $6.9, 최악 상한 $19.35 — 3배 차이다).
#   미리 보수적으로 잡으면 크레딧이 만료로 날아가고, 크게 잡으면 가드가 못 막는다.
#   그래서 S5 가 끝난 뒤 그 실비를 로그에서 읽어 남은 예산을 계산한다.
#     BUDGET = BALANCE - (S5 실비) - MARGIN
#   BALANCE 는 사람이 콘솔에서 확인한 잔액이다. 추정하지 않는다.
#   (BALANCE 를 읽은 시점에 S5 luna $0.346 은 이미 빠져 있으므로 이 식은 그만큼
#    이중으로 뺀다 — 안전한 쪽 오차라 그대로 둔다.)
#
# 단계(astra 제외. 잔액 $35.54 로는 astra 를 넣으면 다른 단계가 밀린다)
#   8  f250_*   free_full 을 공통 250문항으로. sol→terra→luna 순    투영 $16.5
#               여기까지 찍으면 같은 250문항 위에서 arm 0 / brief / full
#               3점 곡선이 완성된다. 이번 주 최대 발견을 72문항에서 250문항으로 올린다
#   9  x50b_*   3모델 연속 교차. Task C 의 '캡처 시각이 모델마다 다르다' 교란 제거  투영 $0.8
#   3  rep_*    36문항 × 5반복. OpenAI 의 실패가 역전(분산)이라 반복 평균으로
#               걷히는지 본다. 걷히면 다중 관측 위협모델에서 유리해진다      투영 $4.4
#   4  ext_*    나머지 384문항 표본 확장. 넷 중 효과가 가장 작아 맨 뒤       투영 $9.6
#
#   투영 합 $31.2. 잔액이 모자라면 가드가 뒤에서부터(=가치 낮은 쪽부터) 자른다.
#
# 입력 : ~/.llm_keys (OPENAI_API_KEY), out/run_oai_s5.out (S5 실비를 읽는다),
#        out/qfile_anth250.json, out/qfile_oai_cross50.json,
#        out/qfile_oai_rep.json, out/qfile_oai_extra_rest.json
# 출력 : out/openai_strict_<tag>_<ts>.pcap · ..._log.jsonl · out/<tag>.csv
#
# 사용 : nohup env BALANCE=35.54 bash run_openai_rest.sh > out/run_oai_rest.out 2>&1 &
#        BALANCE=35.54 STAGES="8 9" bash run_openai_rest.sh    # 단계를 직접 고를 때
#        BUDGET=20 bash run_openai_rest.sh                     # 예산을 직접 줄 때
#
# 작성일: 2026-11-22
set -u
cd "$(dirname "$0")"

BALANCE="${BALANCE:-35.54}"
MARGIN="${MARGIN:-3.0}"
STAGES="${STAGES:-8 9 3 4}"
S5LOG="${S5LOG:-out/run_oai_s5.out}"

# 앞선 캡처가 끝나기를 기다린다. 이미 끝났으면 즉시 통과한다.
if pgrep -f 'run_openai_next\.sh' > /dev/null; then
  echo "[$(date +%F' '%H:%M:%S)] 앞 캡처가 돌고 있다. 끝날 때까지 대기(60초 간격)."
  while pgrep -f 'run_openai_next\.sh' > /dev/null; do sleep 60; done
  # 러너가 종료된 직후에는 tcpdump 가 버퍼를 비우는 중일 수 있다. 조금 더 둔다.
  sleep 30
fi

# 예산 계산. BUDGET 을 직접 준 경우에는 그걸 쓴다.
if [ -z "${BUDGET:-}" ]; then
  S5SPENT=$(sed -n 's/.*누적 \$\([0-9.]*\) \/.*/\1/p' "$S5LOG" 2>/dev/null | tail -1)
  if [ -z "$S5SPENT" ]; then
    echo "[중단] $S5LOG 에서 S5 누적 실비를 못 읽었다. 예산을 계산할 수 없다."
    echo "       BUDGET 을 직접 주고 다시 띄워라:  BUDGET=25 bash run_openai_rest.sh"
    exit 1
  fi
  BUDGET=$(awk "BEGIN{printf \"%.2f\", $BALANCE - $S5SPENT - $MARGIN}")
  echo "[예산] 잔액 \$$BALANCE - S5 실비 \$$S5SPENT - 여유 \$$MARGIN = \$$BUDGET"
  if awk "BEGIN{exit !($BUDGET < 1)}"; then
    echo "[중단] 남은 예산이 \$$BUDGET 다. 돌릴 수 있는 단계가 없다."
    exit 1
  fi
fi

echo "[$(date +%F' '%H:%M:%S)] 대기 끝. 단계 [$STAGES] 시작, 전역 예산 \$$BUDGET"
exec env BUDGET="$BUDGET" bash run_openai_next.sh $STAGES
