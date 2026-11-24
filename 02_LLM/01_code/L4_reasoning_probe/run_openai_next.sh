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
  # 시작 전에 전역 상한을 확인한다.
  #
  # 2026-11-21 수정. 예전 판은 '이미 넘었나'만 봤다. 그래서 S2 에서 누적 $7.24 일 때
  # lenfull_sol 이 상한 $8 을 안 넘었다고 통과했고, 그 한 단계가 혼자 $4.85 를 써서
  # 최종 $12.10 으로 51% 초과했다. 시작 전 검사만으로는 마지막 단계를 못 막는다.
  # 이제는 이 단계의 --max-spend(= 이 단계가 쓸 수 있는 최악값)를 미리 더해서 본다.
  # 그래서 BUDGET 의 의미가 '예상 합계'가 아니라 '최악 합계의 상한'으로 바뀐다 —
  # 실제 지출은 보통 그 절반쯤이므로 BUDGET 은 단계 상한들의 합에 맞춰 잡아라.
  local cap=0 prev=""
  for a in "$@"; do
    [ "$prev" = "--max-spend" ] && cap="$a"
    prev="$a"
  done
  if [ "$cap" = "0" ]; then
    echo "[경고] $tag 에 --max-spend 가 없다. 이 단계는 전역 상한이 못 막는다."
  fi
  if awk "BEGIN{exit !($SPENT + $cap > $BUDGET)}"; then
    echo "[예산중단] 누적 \$$SPENT + 이 단계 상한 \$$cap > 전역 \$$BUDGET — $tag 건너뜀"
    return
  fi
  echo; echo "=================================================="
  echo "[$(date +%H:%M:%S)] 시작: $tag   (누적 \$$SPENT / \$$BUDGET)"
  echo "=================================================="
  # ── 동시 캡처 차단 ────────────────────────────────────────────────
  # 2026-11-22 추가. 이날 런처가 두 번 떠서 f250_sol 과 f250_terra 가 1시간 반
  # 나란히 돌았다. 두 tcpdump 필터가 글자 그대로 같아서(OpenAI 는 Cloudflare 뒤라
  # 모델이 달라도 같은 IP 다) 서로의 패킷을 같이 잡았고, 양쪽 pcap 의 타이밍 피처가
  # 통째로 망가졌다. $7.47 을 날렸다. 런처 쪽 flock 만으로는 부족하다 —
  # **캡처를 띄우기 직전**에 다른 캡처가 있는지 직접 본다. 있으면 전체를 멈춘다.
  # 다음 단계로 넘어가면 안 된다. 동시 실행이 일어났다는 건 이미 뭔가 틀렸다는 뜻이다.
  if pgrep -f 'openai_capture_run_strict\.py' > /dev/null; then
    echo "[중단] 다른 캡처가 이미 돌고 있다 — $tag 를 시작하지 않는다."
    pgrep -af 'openai_capture_run_strict\.py' | sed 's/^/    /'
    exit 1
  fi

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
  # 2026-11-22 상한 조임(3.0→2.6, 4.0→3.2). 잔액이 $35.54 뿐이라 상한이 실제보다
  # 크면 가드가 '들어갈 단계'를 헛되이 자른다. 투영(luna $0.23 · terra $1.81 · sol $2.35)
  # 의 약 1.35배로 맞춘다. 투영은 arm 0 콜당 실측에 Gemini 풀 난도 보정 1.6배를 곱한 값.
  stage rep_luna  --model gpt-6-luna   $COMMON --qfile out/qfile_oai_rep.json \
    --efforts $EFF --repeats 5 --arms 0 --price-in 0.10 --price-out 0.50 --max-spend 0.6
  stage rep_terra --model gpt-6.1-terra $COMMON --qfile out/qfile_oai_rep.json \
    --efforts $EFF --repeats 5 --arms 0 --price-in 1 --price-out 5 --max-spend 2.6
  stage rep_sol   --model gpt-6.1-sol  $COMMON --qfile out/qfile_oai_rep.json \
    --efforts $EFF --repeats 5 --arms 0 --price-in 2 --price-out 10 --max-spend 3.2
fi

# ── S4. 문항 확장 ──────────────────────────────────────────────────
# 넷 중 효과가 가장 작다. OpenAI 의 병목은 표본 수가 아니라 모델이 단계를 얼마나
# 벌려 쓰느냐이기 때문이다(A1 35~43%). 예산이 남을 때만 돌려라.
if want 4; then
  # 2026-11-22 상한 조임(6.0→5.2, 8.0→6.8). 투영 luna $0.49 · terra $3.95 · sol $5.14.
  stage ext_luna  --model gpt-6-luna   $COMMON --qfile out/qfile_oai_extra_rest.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 0.10 --price-out 0.50 --max-spend 1.0
  stage ext_terra --model gpt-6.1-terra $COMMON --qfile out/qfile_oai_extra_rest.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 1 --price-out 5 --max-spend 5.2
  stage ext_sol   --model gpt-6.1-sol  $COMMON --qfile out/qfile_oai_extra_rest.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 2 --price-out 10 --max-spend 6.8
fi

# ── S5. 길이 arm 을 공통 250문항으로 확장 ──────────────────────────
# 왜: S2(72문항)에서 "답 길이를 안 묶으면 탐지가 더 쉬워진다"가 나왔다.
#   A3 가 sol 21.5% → 66.2%, terra 23.4% → 57.8% 다. 이게 이번 주 최대 발견인데
#   전조건 완비 문항이 60~68개뿐이라 그대로는 주장으로 못 쓴다.
#   공통 250문항으로 다시 찍으면 표본이 3.5배가 되고, 더 중요하게는
#   **같은 문항의 arm 0 캡처(luna250/terra250/sol250)가 이미 있으므로 페어 비교**가 된다.
#
# arm 은 free_brief 하나만 쓴다. free_full 이 sol 에서 A3 66.2% 로 더 좋지만
#   250문항이면 $16.8 이라 못 쓴다. free_brief 도 arm 0 대비 충분히 오른다
#   (terra 23.4 → 57.8%, sol 21.5 → 56.1%). arm 사이 비교는 S2 72문항 데이터가 맡는다.
#
# 추정 비용(S2 실측 × 250/72 = 3.47배): luna $0.57 · terra $4.29 · sol $6.43 = $11.3
#   상한 합은 $20.5 다. 새 예산 가드는 상한으로 비교하므로 BUDGET=21 이상이어야
#   세 단계가 다 돈다. BUDGET 을 낮게 잡으면 뒤쪽 모델이 통째로 건너뛴다.
#   nohup env BUDGET=21 bash run_openai_next.sh 5 > out/run_oai_s5.out 2>&1 &
if want 5; then
  for spec in \
    "gpt-6-luna|0.10|0.50|1.5|luna" \
    "gpt-6.1-terra|1|5|8.0|terra" \
    "gpt-6.1-sol|2|10|11.0|sol"
  do
    IFS='|' read -r M PI PO CB NICK <<EOF
$spec
EOF
    only "$NICK" || continue
    stage "b250_${NICK}" --model "$M" $COMMON --qfile out/qfile_anth250.json \
      --efforts $EFF --repeats 1 --arms free_brief \
      --price-in "$PI" --price-out "$PO" --max-spend "$CB"
  done
fi

# ── S6. astra 본 캡처 ──────────────────────────────────────────────
# 네 번째 OpenAI 모델. 단가가 입력 $10/1M · 출력 $50/1M 로 sol 의 정확히 5배다.
# sol250 이 $2.04 였으므로 같은 설계면 $10.2 쯤으로 추정되지만, astra 가 sol 보다
# 더 추론하면 그만큼 더 든다 — 상한을 $14 로 둔다.
#
# ★ 먼저 v2 선별을 돌려라. astra 는 v2 문항 선별 기록이 없다(trivial 만 있고
#   거기선 12문항 전부 격차 100 미만이라 0개 통과였다). 선별 없이 본캡처를 돌린
#   대가가 sonnet 의 불응 60% 였다. 선별 명령은 아래 주석.
#     python3 screen_qset.py --provider openai --model gpt-6-astra \
#       --qset v2 --sample 24 --efforts low,medium,high,xhigh,max
#
#   nohup env BUDGET=14 bash run_openai_next.sh 6 > out/run_oai_s6.out 2>&1 &
if want 6; then
  stage astra250 --model gpt-6-astra $COMMON --qfile out/qfile_anth250.json \
    --efforts $EFF --repeats 1 --arms 0 \
    --price-in 10 --price-out 50 --max-spend 14.0
fi

# ── S7. astra 길이 arm ────────────────────────────────────────────
# S6(astra arm 0) 과 같은 250문항이라 페어 비교가 된다. S2 에서 free_brief 가
# 추론토큰을 2.5~10배로 벌렸으므로 astra 도 arm 0 보다 탐지가 오를 것으로 본다.
# 단가가 sol 의 5배라 가장 비싼 단계다.
#
# 2026-11-22 상한 상향 $30 → $40. S2 실측에서 free_brief/arm0 출력토큰 배수가
# terra 3.23배 · sol 3.80배였다(luna 만 1.46배로 낮다 — 경량 모델은 arm 0 에서도
# 이미 추론을 많이 태운다). astra 는 강한 모델이라 terra·sol 쪽을 따를 것으로 본다.
# astra arm 0 출력을 콜당 140토큰(선별 실측 126.9, sol anth250 환산 148.5)으로 잡으면
#   1,250콜 × 140 × 3.2~3.8배 = 56만~66.5만 출력토큰 × $50/1M = $28~33.
# $30 상한은 이 구간 한가운데라 단계 중간에서 잘린다. 투영의 1.2배로 올린다.
if want 7; then
  stage astra_brief --model gpt-6-astra $COMMON --qfile out/qfile_anth250.json \
    --efforts $EFF --repeats 1 --arms free_brief \
    --price-in 10 --price-out 50 --max-spend 40.0
fi

# ── S8. free_full 을 공통 250문항으로 ──────────────────────────────
# S2 에서 가장 센 조건이 sol 의 free_full 이었다(A1 34.8% · A2 91.5% · A3 66.2%,
# 전부 전체 최고). 그런데 전조건 완비 문항이 68개뿐이라 그대로는 못 쓴다.
# S5(free_brief 250) 와 기존 arm 0 250 이 이미 있으므로, 여기까지 찍으면
# **같은 250문항 위에서 arm 0 / brief / full 3점 곡선**이 완성된다.
#
# 투영. 2026-11-22 에 S5 b250_luna 실측($0.346)으로 보정계수를 잡았다.
#   S2 lenbrief_luna(360콜) $0.163 → b250_luna(1250콜) $0.346 = 2.120배.
#   콜 수는 3.472배인데 비용은 2.120배다 — anth250 은 fermi 치우침이라 Gemini 풀보다
#   쉬워서 추론을 덜 태운다(콜당 출력토큰 882.6 → 538.9, 0.611배). 3.472 × 0.611 = 2.120.
#   이 계수를 S2 lenfull 실측에 곱한다: luna $0.73 · terra $5.46 · sol $10.29.
#   상한은 그 1.3배. (계수는 luna free_brief 하나로 잡았다 — 모델·arm 공통이라는
#   가정이 들어 있고, S5 terra 가 끝나면 검증된다.)
# 비싼 쪽부터 돌린다 — 시간이나 크레딧이 먼저 끊겨도 제일 센 결과는 건진다.
if want 8; then
  for spec in \
    "gpt-6.1-sol|2|10|14.0|sol" \
    "gpt-6.1-terra|1|5|7.5|terra" \
    "gpt-6-luna|0.10|0.50|1.2|luna"
  do
    IFS='|' read -r M PI PO CF NICK <<EOF
$spec
EOF
    only "$NICK" || continue
    stage "f250_${NICK}" --model "$M" $COMMON --qfile out/qfile_anth250.json \
      --efforts $EFF --repeats 1 --arms free_full \
      --price-in "$PI" --price-out "$PO" --max-spend "$CF"
  done
fi

# ── S9. 4모델 교차 재캡처 ──────────────────────────────────────────
# S1(11-20) 은 luna·terra·sol 셋뿐이고 astra 가 없다. astra 를 S6 에서 따로
# 찍으면 또 '모델마다 캡처 시각이 다르다'가 생겨 Task C 교란이 되살아난다.
# 네 모델을 같은 50문항으로 2~3시간 안에 연속으로 찍어 그 구멍을 막는다.
# 싸다 — 250콜씩 4개, 합쳐 약 $2.8.
if want 9; then
  stage x50b_luna  --model gpt-6-luna    $COMMON --qfile out/qfile_oai_cross50.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 0.10 --price-out 0.50 --max-spend 0.3
  stage x50b_terra --model gpt-6.1-terra $COMMON --qfile out/qfile_oai_cross50.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 1 --price-out 5 --max-spend 1.0
  stage x50b_sol   --model gpt-6.1-sol   $COMMON --qfile out/qfile_oai_cross50.json \
    --efforts $EFF --repeats 1 --arms 0 --price-in 2 --price-out 10 --max-spend 1.2
  # astra 는 기본으로 안 돈다. 잔액 $35.54(2026-11-22)로는 astra 를 어디에 넣어도
  # 다른 단계 하나를 밀어낸다 — 250문항 풀캡처는 $9.1, 이 50문항도 $1.82 다.
  # 돌리려면 ONLY 에 astra 를 넣어라:  ONLY="luna terra sol astra" ... 9
  if only astra; then
    stage x50b_astra --model gpt-6-astra $COMMON --qfile out/qfile_oai_cross50.json \
      --efforts $EFF --repeats 1 --arms 0 --price-in 10 --price-out 50 --max-spend 2.6
  fi
fi

echo; echo "[$(date +%H:%M:%S)] 전체 종료."
