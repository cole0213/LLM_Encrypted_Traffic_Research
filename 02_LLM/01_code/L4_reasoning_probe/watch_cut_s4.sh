#!/usr/bin/env bash
# watch_cut_s4.sh — 돌고 있는 run_openai_rest.sh 가 S4(ext_*) 로 넘어가는 순간
#   끼어들어서, 남은 크레딧을 S8(f250_* free_full) + S9(x50b_*) 에 몰아준다.
#
# 왜 필요한가
#   run_openai_next.sh 의 `want()` 는 '이 단계를 돌릴까'를 거르는 필터일 뿐,
#   실행 순서는 인자 순서가 아니라 **파일에 적힌 순서**다. 그래서 STAGES="8 9 3 4"
#   를 줘도 실제로는 3 → 4 → 8 → 9 로 돈다. S4(ext, 표본 확장)가 약 $8.95 를
#   먼저 먹으면 전역 가드가 `누적 8.95 + f250_sol 상한 14 > 예산 19.77` 로 보고
#   **S8 의 sol 을 통째로 건너뛴다.** 이번 주 최대 발견(free_full 에서 A3 66.2%)의
#   250문항 확장이 그대로 날아간다. S4 는 arm 0 표본을 250→634 로 늘리는 것뿐이라
#   넷 중 가치가 가장 낮다. 그래서 S4 를 끊고 그 돈을 S8 로 돌린다.
#
# 왜 복사본을 만드는가
#   bash 는 실행 중인 스크립트 파일을 바이트 오프셋으로 되읽는다. 돌고 있는
#   run_openai_next.sh 를 제자리에서 고치면 실행이 깨진다. 원본은 건드리지 않고
#   run_openai_next_b.sh 로 복사한 뒤 거기서 상한만 바꾼다.
#
# 새 상한 (2026-11-22 실측 기준)
#   b250 실측 × S2 의 free_full/free_brief 비율 = f250 투영
#     sol   $7.483 × 2.62 = $19.6   terra $4.944 × 2.08 = $10.3   luna $0.346 × 2.10 = $0.73
#   남는 예산(S3 까지 쓰고 약 $16.7)으로는 sol 하나도 다 못 찍는다. 어차피 잘리므로
#   **어디서 자를지**를 고른다. sol $9.5 · terra $5.0 으로 나누면 둘 다 약 120문항씩
#   온전한 5조건 블록으로 남는다(--block-shuffle 이 블록 단위로 자른다).
#   S2 의 전조건 완비 문항이 60~68개였으니 둘 다 약 1.8배다.
#   한 모델에 몰아 194문항을 찍는 것보다, 두 모델 120문항씩이 주장에 더 쓸모 있다.
#   S9 상한은 실측 단가(arm 0, 250콜)에 맞게 조인다: luna $0.04 · terra $0.31 · sol $0.41.
#
# 왜 astra 를 S9 에만 넣는가 (2026-11-22 추가)
#   astra 는 본 캡처 데이터가 0 이다 — 선별 24문항($0.87)이 전부다. 그런데 그 선별에서
#   max/low 배수 중앙이 4.7배로 sol(3.4) · terra(3.5)보다 컸다. "A1 순위가 추론토큰
#   격차 순위와 거의 같다"는 관찰대로면 **astra 가 제일 잘 새는 모델일 수 있다.**
#   단가 1등이 탐지도 1등이면 그 자체가 결과다. 250문항 풀캡처는 $9.06 이라 못 넣지만,
#   S9 의 50문항(250콜)은 선별 실측 단가로 환산해 **$1.82** 다. 이건 남는 여유에 들어간다.
#   덤으로 S9 가 원래 목적(네 모델을 같은 50문항으로 연속 캡처해 Task C 의
#   '모델마다 캡처 시각이 다르다' 교란 제거)을 비로소 채운다. 3모델이면 반쪽이다.
#   한계: 50문항은 Task A 엔 얇다(S2 가 60~68문항). astra 의 A1/A2/A3 첫 수치는
#   나오지만 주장으로 세우기엔 부족하고, 목적은 Task C 교차다.
#
#   **기본값은 astra 없음이다.** 돌리려면 띄울 때 환경변수로 켠다:
#     ONLY="luna terra sol astra" MARGIN=1.5 nohup bash watch_cut_s4.sh ...
#   ONLY 는 exec 로 넘어가는 환경에 그대로 실려 run_openai_next_b.sh 의 only() 가 읽는다.
#   S8 의 spec 목록엔 astra 가 없으므로 S8 은 영향을 안 받는다(only() 는 목록에 있는
#   nick 만 거른다). MARGIN 을 1.5 로 줄여야 가드가 astra 단계를 통과시킨다.
#   가드 계산(예상): 예산 약 $18.4.  f250 sol 9.5 → terra 14.5 → luna 15.23
#     → x50b luna 15.27 · terra 15.58 · sol 15.99 → astra 15.99+2.2=18.19 ≤ 18.4 통과.
#   여유를 1.5 로 줄인 위험: 상한은 단계마다 하드 리밋이라 초과가 날 구조는 아니다.
#   잔액 판독이 조금 틀려 모자라면 콜이 실패하며 단계가 중간에 끊기는데,
#   --block-shuffle 이라 끊긴 데까지는 5조건 온전한 블록으로 남는다.
#
# 입력 : out/run_oai_rest.out (진행 감시 + 누적 실비), out/run_oai_s5.out (S5 실비)
# 출력 : out/run_oai_s8.out (새 런의 로그), run_openai_next_b.sh (상한만 바꾼 복사본)
#
# 사용 : nohup bash watch_cut_s4.sh > out/watch_cut_s4.out 2>&1 &
#
# 작성일: 2026-11-22
set -u
cd "$(dirname "$0")"

BALANCE="${BALANCE:-35.54}"
MARGIN="${MARGIN:-3.0}"
RESTLOG="${RESTLOG:-out/run_oai_rest.out}"
S5LOG="${S5LOG:-out/run_oai_s5.out}"
NEWLOG="${NEWLOG:-out/run_oai_s8.out}"

say() { echo "[$(date +%F' '%H:%M:%S)] $*"; }

# ── 1. S4 가 시작되거나 러너가 사라질 때까지 기다린다 ──────────────
say "감시 시작. out/run_oai_rest.out 에 '시작: ext_' 가 뜨면 끊는다."
while true; do
  if grep -q '시작: ext_' "$RESTLOG" 2>/dev/null; then
    say "S4(ext_*) 진입 감지. 끊는다."
    break
  fi
  if ! pgrep -f 'run_openai_next\.sh' > /dev/null; then
    say "러너가 이미 끝났다. 바로 S8 로 넘어간다."
    break
  fi
  sleep 20
done

# ── 2. 러너와 tcpdump 를 정리한다 ──────────────────────────────────
# 러너를 먼저 죽이고 tcpdump 를 따로 죽인다. 러너가 단계마다 tcpdump 를 띄우므로
# 러너만 죽이면 고아 tcpdump 가 남아 파일을 계속 키운다.
pkill -f 'run_openai_rest\.sh' 2>/dev/null
pkill -f 'run_openai_next\.sh' 2>/dev/null
sleep 2
pkill -f 'capture_run_strict\.py' 2>/dev/null
sleep 2
pkill -f 'tcpdump.*openai_strict' 2>/dev/null
sleep 3
say "잔존 확인:"
pgrep -af 'run_openai_next\.sh|capture_run_strict\.py|tcpdump' || echo "  (없음)"

# ── 3. 예산을 다시 계산한다 ────────────────────────────────────────
S5SPENT=$(sed -n 's/.*누적 \$\([0-9.]*\) \/.*/\1/p' "$S5LOG" 2>/dev/null | tail -1)
RESTSPENT=$(sed -n 's/.*누적 \$\([0-9.]*\) \/.*/\1/p' "$RESTLOG" 2>/dev/null | tail -1)
[ -z "$S5SPENT" ] && S5SPENT=0
[ -z "$RESTSPENT" ] && RESTSPENT=0
BUDGET=$(awk "BEGIN{printf \"%.2f\", $BALANCE - $S5SPENT - $RESTSPENT - $MARGIN}")
say "예산: 잔액 \$$BALANCE - S5 \$$S5SPENT - S3 \$$RESTSPENT - 여유 \$$MARGIN = \$$BUDGET"
if awk "BEGIN{exit !($BUDGET < 1)}"; then
  say "[중단] 남은 예산이 \$$BUDGET 다. 돌릴 단계가 없다."
  exit 1
fi

# ── 4. 상한만 바꾼 복사본을 만든다 ─────────────────────────────────
cp run_openai_next.sh run_openai_next_b.sh
# S8 (294~308행 부근): spec 문자열 안의 상한
sed -i 's#"gpt-6\.1-sol|2|10|14\.0|sol"#"gpt-6.1-sol|2|10|9.5|sol"#'        run_openai_next_b.sh
sed -i 's#"gpt-6\.1-terra|1|5|7\.5|terra"#"gpt-6.1-terra|1|5|5.0|terra"#'   run_openai_next_b.sh
# S9: x50b_* 상한을 실측 단가에 맞게 조인다. S1 의 x50_* 과 줄이 똑같으므로
# 반드시 'x50b' 가 든 줄 다음에만 바꾼다 — 행 범위가 아니라 패턴으로 묶는다.
sed -i '/x50b_luna/,+1 s/--max-spend 0\.3$/--max-spend 0.1/'  run_openai_next_b.sh
sed -i '/x50b_terra/,+1 s/--max-spend 1\.0$/--max-spend 0.5/' run_openai_next_b.sh
sed -i '/x50b_sol/,+1  s/--max-spend 1\.2$/--max-spend 0.7/'  run_openai_next_b.sh
# astra 상한은 선별 실측 환산($1.82)의 1.21배로 조인다. ONLY 에 astra 가 없으면
# 이 단계 자체가 안 돌므로, 상한만 미리 맞춰두고 켜고 끄는 건 ONLY 에 맡긴다.
sed -i '/x50b_astra/,+1 s/--max-spend 2\.6$/--max-spend 2.2/' run_openai_next_b.sh

if ! bash -n run_openai_next_b.sh; then
  say "[중단] 복사본 문법 오류. 아무것도 안 돌린다."
  exit 1
fi
say "새 상한:"
grep -nE 'gpt-6\.1-(sol|terra)\|' run_openai_next_b.sh | sed 's/^/  /'
grep -nA1 'x50b_' run_openai_next_b.sh | grep 'max-spend' | sed 's/^/  /'

# ── 5. S8 → S9 를 돌린다 ───────────────────────────────────────────
say "단계 [8 9] 시작, 전역 예산 \$$BUDGET. 로그: $NEWLOG"
exec env BUDGET="$BUDGET" bash run_openai_next_b.sh 8 9 > "$NEWLOG" 2>&1
