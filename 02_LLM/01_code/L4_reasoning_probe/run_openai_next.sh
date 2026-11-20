#!/usr/bin/env bash
# run_openai_next.sh — OpenAI 2차 캡처(증강·대조군)를 단계별로 돌린다.
#
# 왜 OpenAI 부터인가
#   (1) Anthropic 크레딧이 $12.45 밖에 안 남았다(2026-11-20).
#   (2) OpenAI 3모델은 본 캡처에서 불응 0%·수율 98~100% 로 가장 깨끗했다.
#   (3) cross-model 전이 분석에서 OpenAI 모델이 '가장 좋은 교사'로 나왔다
#       (luna 로 학습 → 다른 6모델 순위 전이 평균 93.5%).
#
# 네 단계, 각각 독립이다. 번호로 골라 돌린다.
#   S1 교차 캡처    — 3모델을 같은 50문항으로 연속 캡처. Task C 의 '캡처 시각이
#                     모델마다 달라 망 상태 교란을 못 지웠다'를 제거한다.
#   S2 길이 arm     — 답 길이 통제를 푼 대조군(free_brief / free_full) + 기준선 arm 0.
#                     "답을 1글자로 고정한 건 비현실적"이라는 반론을 정면으로 막는다.
#                     쓰는 문항이 OpenAI 로는 처음이라 문항 확장 효과도 같이 난다.
#   S3 반복 측정    — 같은 문항·같은 조건을 5번. OpenAI 의 실패 양상은 '동률'이 아니라
#                     '역전'(분산)이라, 반복 평균으로 걷히는지 본다. 걷히면
#                     다중 관측 위협모델에서 OpenAI 가 Anthropic 보다 유리해진다.
#   S4 문항 확장    — 나머지 384문항. 표본을 늘린다. 넷 중 효과가 가장 작다.
#
# 문항 집합
#   S1 은 공통 250 에서 층화추출(기존 데이터와 바로 비교해야 하므로 성격을 맞춘다).
#   S2~S4 는 Gemini 전용 521문항 풀에서 뽑는다 — 공통 250 은 dilemma 를 빼면
#   fermi 가 68% 라 치우쳐 있고, Gemini 풀은 논리퍼즐 18종이 고르게 들어 있다.
#   S3 의 36문항은 S2 의 72문항의 부분집합이라 결과를 겹쳐 읽을 수 있다.
#
# 입력 : ~/.llm_keys (OPENAI_API_KEY)
#        out/qfile_oai_cross50.json  out/qfile_oai_aug.json
#        out/qfile_oai_rep.json      out/qfile_oai_extra_rest.json
# 출력 : out/openai_strict_<tag>_<ts>.pcap, ..._log.jsonl, out/<tag>.csv
#
# 사용 : bash run_openai_next.sh 1          # S1 만
#        bash run_openai_next.sh 1 3        # S1, S3
#        nohup bash run_openai_next.sh 1 2 3 > out/run_oai2.out 2>&1 &
#
# 비용 (본 캡처 실측 단가에서 계산한 '추정'. 실제는 --max-spend 가 막는다)
#   콜당 실측: luna $0.000158 · terra $0.001254 · sol $0.001634  (arm 0 기준)
#   S1   750콜 (3캡처)  약 $0.76     S2 3,240콜 (9캡처)  약 $6.2
#   S3 2,700콜 (3캡처)  약 $2.7      S4 5,760콜 (3캡처)  약 $5.9
#   자유 응답 arm 은 출력 토큰이 늘어 콜당 2~3.5배다 — S2 추정의 불확실성이 가장 크다.
#   추정은 지금까지 네 번 다 빗나갔다. 숫자를 믿지 말고 상한을 믿어라.
#   단계별 상한 합: S1 $2.5 · S2 $16.8 · S3 $7.6 · S4 $15.0 (상한이지 예상액이 아니다)
#
# 작성일: 2026-11-20
set -u
cd "$(dirname "$0")"
LOCAL_IP="${LOCAL_IP:-163.152.223.17}"

[ -f "$HOME/.llm_keys" ] && . "$HOME/.llm_keys"
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "[중단] OPENAI_API_KEY 가 없다. ~/.llm_keys 를 확인하라."
  exit 1
fi

# 캡처 한 단계를 돌리고 방금 생긴 pcap 을 CSV 까지 파싱한다.
#   $1 태그  $2.. 러너 인자
# ── 전역 예산 ─────────────────────────────────────────────────────
# 러너의 --max-spend 는 '캡처 하나' 안에서만 센다. 캡처가 9개면 상한도 9개라
# 합계가 통제되지 않는다. 여기서 캡처마다 실제 비용을 읽어 누적하고, 전역 상한을
# 넘으면 남은 캡처를 통째로 건너뛴다. 비용은 추정하지 말고 막으라는 원칙의 연장이다.
#   BUDGET=12 bash run_openai_next.sh 2
SPENT=0
BUDGET="${BUDGET:-8.0}"
echo "[전역 예산] \$$BUDGET (BUDGET 환경변수로 변경)"

# 캡처 한 단계를 돌리고, 비용을 누적한 뒤, 방금 생긴 pcap 을 CSV 까지 파싱한다.
#   $1 태그  $2.. 러너 인자
stage() {
  local tag="$1"; shift
  # 시작 전에 전역 상한을 확인한다. 이미 넘었으면 콜을 한 개도 안 보낸다.
  if awk "BEGIN{exit !($SPENT >= $BUDGET)}"; then
    echo "[예산중단] 누적 \$$SPENT >= 전역 상한 \$$BUDGET — $tag 건너뜀"
    return
  fi
  echo; echo "=================================================="
  echo "[$(date +%H:%M:%S)] 시작: $tag   (누적 \$$SPENT / \$$BUDGET)"
  echo "=================================================="
  local tmp="out/.stage_${tag}.log"
  # tee 로 흘려보내면서 같은 내용을 파일에도 남겨 비용 줄을 읽는다.
  # 파이프를 쓰면 $? 가 tee 의 것이 되므로 PIPESTATUS 로 러너의 종료코드를 본다.
  bash openai_capture_strict.sh "$tag" "$@" 2>&1 | tee "$tmp"
  local rc=${PIPESTATUS[0]}

  # 러너가 마지막에 찍는 "토큰: ... / 비용 $X" 줄에서 금액을 뽑는다.
  local c
  c=$(sed -n 's/.*비용 \$\([0-9.]*\).*/\1/p' "$tmp" | tail -1)
  if [ -n "$c" ]; then
    SPENT=$(awk "BEGIN{printf \"%.4f\", $SPENT + $c}")
    echo "[비용] $tag \$$c  →  누적 \$$SPENT / \$$BUDGET"
  else
    # 금액을 못 읽으면 누적이 멈춰 상한이 무의미해진다. 조용히 넘어가면 안 된다.
    echo "[경고] $tag 비용 줄을 못 읽었다. 누적에 반영되지 않았다 — 전역 상한이 느슨해진다."
  fi
  rm -f "$tmp"

  if [ "$rc" -eq 0 ]; then
    local pcap
    pcap=$(ls -t out/openai_strict_${tag}_*.pcap 2>/dev/null | head -1)
    if [ -n "$pcap" ]; then
      echo "[$(date +%H:%M:%S)] 파싱: $pcap"
      python3 parse_pcap.py "$pcap" "out/openai_strict_${tag}_log.jsonl" \
        --local-ip "$LOCAL_IP" --out "out/${tag}.csv" || echo "[경고] $tag 파싱 실패"
    else
      echo "[경고] $tag pcap 을 못 찾았다."
    fi
  else
    echo "[실패] $tag 단계가 비정상 종료(코드 $rc). 다음 단계로 넘어간다."
  fi
}

want() { [ $# -eq 0 ] && return 0; case " $PICK " in *" $1 "*) return 0;; *) return 1;; esac; }
PICK="${*:-}"

# 모델 하나만 먼저 돌려 실제 단가를 보고 싶을 때 쓴다. 자유응답 arm 은 출력 토큰이
# 얼마나 불어날지 추정이 가장 불확실하므로, 제일 싼 luna 로 먼저 재는 편이 안전하다.
#   ONLY=luna bash run_openai_next.sh 2
#   ONLY="terra sol" bash run_openai_next.sh 2
only() { case " ${ONLY:-luna terra sol} " in *" $1 "*) return 0;; *) return 1;; esac; }
[ -n "${ONLY:-}" ] && echo "[모델 제한] $ONLY"

EFF="low,medium,high,xhigh,max"
COMMON="--qset v2 --api responses --sleep 3 --block-shuffle"

# ── S1. 교차 캡처 — 3모델 연속, 같은 50문항 ───────────────────────
# 모델 사이에 시간을 안 둔다. 세 캡처가 한 시간 안에 끝나므로 망 상태가 거의 같고,
# Task C 99.2% 중 얼마가 망 상태 때문이었는지 가려진다.
# (한 pcap 안에 섞어 찍는 것이 이상적이지만, 그러려면 러너를 다시 짜야 한다.
#  연속 캡처만으로도 11-18~11-20 에 걸친 지금의 교란보다 훨씬 낫다.)
if want 1; then
  stage x50_luna  --model gpt-6-luna   $COMMON --qfile out/qfile_oai_cross50.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 0.10 --price-out 0.50 --max-spend 0.3
  stage x50_terra --model gpt-6.1-terra $COMMON --qfile out/qfile_oai_cross50.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 1 --price-out 5 --max-spend 1.0
  stage x50_sol   --model gpt-6.1-sol  $COMMON --qfile out/qfile_oai_cross50.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 2 --price-out 10 --max-spend 1.2
fi

# ── S2. 길이 arm 대조군 ────────────────────────────────────────────
# arm 0(1글자) 을 같이 찍어 같은 문항·같은 세션의 기준선을 만든다. 기존 250문항
# 데이터를 기준선으로 쓰면 문항도 시각도 달라 비교가 흐려진다.
#
# ★ arm 은 반드시 캡처를 나눈다. 한 캡처에 섞으면 free_full 의 거대 응답이
#   다음 콜의 측정창을 오염시킨다(openai_capture_strict.sh 주석, HANDOFF 3-13(b)).
#   그래서 모델 3 × arm 3 = 9개 캡처다. 연달아 돌아가므로 망 상태는 거의 같다.
#
# free_* arm 은 build_arm 이 max_tok 을 2048+1024 로 올리지만 러너가
# max(그 값, --max-tok) 을 쓰므로 결국 8192 다 — provider 공통 통제가 유지된다.
if want 2; then
  # 모델별 (모델명, 입력단가, 출력단가, arm0 상한, brief 상한, full 상한)
  # 상한은 실측 콜당 단가에서 계산한 추정의 약 2배다. 추정이 틀려도 폭주는 막힌다.
  for spec in \
    "gpt-6-luna|0.10|0.50|0.25|0.35|0.60|luna" \
    "gpt-6.1-terra|1|5|1.2|1.8|3.0|terra" \
    "gpt-6.1-sol|2|10|1.5|2.6|5.0|sol"
  do
    IFS='|' read -r M PI PO C0 CB CF NICK <<EOF
$spec
EOF
    only "$NICK" || continue
    stage "len0_${NICK}"     --model "$M" $COMMON --qfile out/qfile_oai_aug.json \
      --efforts $EFF --repeats 1 --arms 0 \
      --price-in "$PI" --price-out "$PO" --max-spend "$C0"
    stage "lenbrief_${NICK}" --model "$M" $COMMON --qfile out/qfile_oai_aug.json \
      --efforts $EFF --repeats 1 --arms free_brief \
      --price-in "$PI" --price-out "$PO" --max-spend "$CB"
    stage "lenfull_${NICK}"  --model "$M" $COMMON --qfile out/qfile_oai_aug.json \
      --efforts $EFF --repeats 1 --arms free_full \
      --price-in "$PI" --price-out "$PO" --max-spend "$CF"
  done
fi

# ── S3. 반복 측정 ──────────────────────────────────────────────────
# 블록 셔플은 반복도 블록 안에 묶는다. 중간에 끊겨도 찍힌 문항은 5반복이 다 모인다.
if want 3; then
  stage rep_luna  --model gpt-6-luna   $COMMON --qfile out/qfile_oai_rep.json \
    --efforts $EFF --repeats 5 --arms 0 --price-in 0.10 --price-out 0.50 --max-spend 0.6
  stage rep_terra --model gpt-6.1-terra $COMMON --qfile out/qfile_oai_rep.json \
    --efforts $EFF --repeats 5 --arms 0 --price-in 1 --price-out 5 --max-spend 3.0
  stage rep_sol   --model gpt-6.1-sol  $COMMON --qfile out/qfile_oai_rep.json \
    --efforts $EFF --repeats 5 --arms 0 --price-in 2 --price-out 10 --max-spend 4.0
fi

# ── S4. 문항 확장 ──────────────────────────────────────────────────
# 넷 중 효과가 가장 작다. OpenAI 의 병목은 표본 수가 아니라 모델이 단계를 얼마나
# 벌려 쓰느냐이기 때문이다(A1 35~43%). 예산이 남을 때만 돌려라.
if want 4; then
  stage ext_luna  --model gpt-6-luna   $COMMON --qfile out/qfile_oai_extra_rest.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 0.10 --price-out 0.50 --max-spend 1.0
  stage ext_terra --model gpt-6.1-terra $COMMON --qfile out/qfile_oai_extra_rest.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 1 --price-out 5 --max-spend 6.0
  stage ext_sol   --model gpt-6.1-sol  $COMMON --qfile out/qfile_oai_extra_rest.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 2 --price-out 10 --max-spend 8.0
fi

echo; echo "[$(date +%H:%M:%S)] 전체 종료."
