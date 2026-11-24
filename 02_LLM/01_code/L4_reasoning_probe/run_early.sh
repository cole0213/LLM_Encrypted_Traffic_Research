#!/usr/bin/env bash
# run_early.sh — 기존 pcap 을 재파싱해서 (1) RF 정본 Task A, (2) 조기 탐지 곡선을 낸다.
#
# 왜 필요한가
#   지금까지 보고한 Task A 정확도는 node 로 급히 짠 대각 공분산 가우시안 분류기
#   수치다. 피처끼리 상관이 0.97 이상이라 조건부 독립 가정이 크게 깨져 있어
#   참고치로만 써야 한다. early_eval.py 는 e1_from_csv.py 와 같은
#   RandomForest + family 단위 GroupKFold 로 다시 재므로 `--cutoffs 0` 이 곧 정본이다.
#   같은 재파싱으로 조기 탐지(RQ6) 곡선까지 공짜로 나온다.
#
# 비용
#   API 콜 0. 네트워크 0. CPU 만 쓴다. 그래서 캡처가 돌고 있어도 같이 돌릴 수 있다.
#   다만 캡처 러너의 응답 페이싱이 CPU 경합으로 흔들리지 않게 `nice -n 19` 로
#   우선순위를 가장 낮게 깔고 **한 번에 하나씩** 돌린다(병렬 금지).
#   전선 피처는 커널 타임스탬프(pcap)에서 나오므로 이 작업이 피처를 오염시키지 않는다.
#
# 입력 : out/*.pcap + 같은 이름의 *_log.jsonl 쌍
# 출력 : out/early_<tag>.csv (long 형식, cutoff_ms 열 포함)
#        out/taskA_rf_<tag>.csv (cutoff 0 = Task A 정본)
#        out/early_<tag>.txt / out/taskA_rf_<tag>.txt (표준출력 표)
#
# 사용 : nohup bash run_early.sh > out/run_early.out 2>&1 &
#        TAGS="sol250 terra250" bash run_early.sh    # 일부만
#
# 작성일: 2026-11-22
set -u
cd "$(dirname "$0")"

IP="${IP:-163.152.223.17}"
CUTS="${CUTS:-200,500,1000,2000,5000,10000,0}"
# tag|pcap glob|log|평가 추가인자  — 본 캡처만 돈다. 선별·스모크·파일럿은 뺀다.
#
# 네 번째 필드는 early_eval.py 에 그대로 넘어간다. 비워도 된다.
#   arm 0 캡처는 답이 한 글자라 기본값(--clean-only)이 맞다.
#   free_brief / free_full 캡처는 답이 길다. --clean-only 가 answer_chars==1 을
#   요구하므로 전 행이 걸러져 "조건에 맞는 행이 없다"로 끝난다(2026-11-22 에 겪었다).
#   그래서 길이 arm 캡처에는 --no-clean-only 를 붙인다.
#
# 순서: OpenAI arm 0 250 → Anthropic arm 0 250 → S5 free_brief 250
#       → S8 free_full 250(상한에서 110문항) → S9 교차 50문항 4모델.
SPECS="
luna250|openai_strict_luna250_*.pcap|openai_strict_luna250_log.jsonl|
terra250|openai_strict_terra250_*.pcap|openai_strict_terra250_log.jsonl|
sol250|openai_strict_sol250_*.pcap|openai_strict_sol250_log.jsonl|
sonnet250|anthropic_strict_sonnet250_*.pcap|anthropic_strict_sonnet250_log.jsonl|
opus250|anthropic_strict_opus250_*.pcap|anthropic_strict_opus250_log.jsonl|
haiku250|anthropic_strict_haiku250_*.pcap|anthropic_strict_haiku250_log.jsonl|
b250_luna|openai_strict_b250_luna_*.pcap|openai_strict_b250_luna_log.jsonl|--no-clean-only
b250_terra|openai_strict_b250_terra_*.pcap|openai_strict_b250_terra_log.jsonl|--no-clean-only
b250_sol|openai_strict_b250_sol_*.pcap|openai_strict_b250_sol_log.jsonl|--no-clean-only
f250_sol|openai_strict_f250_sol_20261122_102058.pcap|openai_strict_f250_sol_log.jsonl|--no-clean-only
x50b_luna|openai_strict_x50b_luna_*.pcap|openai_strict_x50b_luna_log.jsonl|
x50b_terra|openai_strict_x50b_terra_*.pcap|openai_strict_x50b_terra_log.jsonl|
x50b_sol|openai_strict_x50b_sol_*.pcap|openai_strict_x50b_sol_log.jsonl|
x50b_astra|openai_strict_x50b_astra_*.pcap|openai_strict_x50b_astra_log.jsonl|
"

say() { echo "[$(date +%F' '%H:%M:%S)] $*"; }

for spec in $SPECS; do
  # 필드가 셋뿐인 줄이면 EXTRA 는 빈 문자열로 채워진다(read 의 기본 동작).
  IFS='|' read -r TAG PGLOB LOG EXTRA <<EOF
$spec
EOF
  # TAGS 를 줬으면 그 안에 든 것만 돈다.
  if [ -n "${TAGS:-}" ]; then
    case " $TAGS " in *" $TAG "*) ;; *) continue;; esac
  fi

  PCAP=$(ls -1 out/$PGLOB 2>/dev/null | tail -1)
  if [ -z "$PCAP" ] || [ ! -f "out/$LOG" ]; then
    say "[건너뜀] $TAG — pcap 또는 로그 없음 (pcap='$PCAP')"
    continue
  fi

  # ── 1. 재파싱 ────────────────────────────────────────────────────
  if [ -s "out/early_${TAG}.csv" ]; then
    say "[있음] out/early_${TAG}.csv — 재파싱 건너뜀"
  else
    say "재파싱 $TAG  ($(du -h "$PCAP" | cut -f1))"
    if ! nice -n 19 python3 early_detect.py "$PCAP" "out/$LOG" \
        --local-ip "$IP" --cutoffs "$CUTS" --out "out/early_${TAG}.csv" \
        > "out/early_${TAG}.txt" 2>&1; then
      say "[실패] $TAG 재파싱. 마지막 줄:"
      tail -3 "out/early_${TAG}.txt" | sed 's/^/    /'
      continue
    fi
  fi

  # ── 2. Task A 정본 (cutoff 0 = 자르지 않은 전체 창) ──────────────
  say "Task A 정본 $TAG"
  # $EXTRA 는 따옴표 없이 둔다 — 비어 있으면 인자 자체가 사라져야 하기 때문이다.
  nice -n 19 python3 early_eval.py "out/early_${TAG}.csv" --cutoffs 0 $EXTRA \
    --out "out/taskA_rf_${TAG}.csv" > "out/taskA_rf_${TAG}.txt" 2>&1 \
    || say "[실패] $TAG Task A"

  # ── 3. 조기 탐지 곡선 (전 cutoff) ────────────────────────────────
  say "조기 탐지 곡선 $TAG"
  nice -n 19 python3 early_eval.py "out/early_${TAG}.csv" $EXTRA \
    --out "out/earlycurve_${TAG}.csv" > "out/earlycurve_${TAG}.txt" 2>&1 \
    || say "[실패] $TAG 곡선"

  say "완료 $TAG"
  echo "---- Task A ($TAG) ----"
  cat "out/taskA_rf_${TAG}.txt"
  echo "---- 조기 탐지 ($TAG) ----"
  cat "out/earlycurve_${TAG}.txt"
  echo
done

say "전체 종료."
