#!/usr/bin/env bash
# run_openai_final.sh — OpenAI 크레딧 만료(2026-11-23) 전 마지막 캡처.
#
# 무엇을 돌리는가
#   S8 의 f250_sol 하나 + S9 의 x50b 네 모델. 그게 전부다.
#     f250_sol   free_full · 공통 250문항 · 상한 $8.5  → 약 111문항까지 찍힌다
#     x50b_*     arm 0 · 교차 50문항 · luna/terra/sol/astra 연속
#
# 왜 이 조합인가
#   남은 크레딧이 $12.74 다(2026-11-22 18:50, 아래 '사고' 참조). 실측 단가로
#   f250_sol 은 250문항 전부 찍으면 $19.15 라 애초에 다 못 찍는다. 그래서
#   **어디서 자를지**를 고른 결과다.
#   - sol 을 고른 이유: RF 정본 Task A 에서 2위(40.3%, 우연대비 2.02배)고,
#     S2 길이 arm 에서 free_full 이 전체 최고였다(A1 34.8% · A2 91.5% · A3 66.2%).
#     arm 0 250문항과 free_brief 250문항(S5) 이 이미 있으므로, 여기까지 찍으면
#     **같은 250문항 위에서 arm0 / brief / full 3점 곡선**이 sol 에서 완성된다.
#     111문항은 S2 의 전조건 완비 68문항보다 1.6배다.
#   - terra·luna 의 free_full 을 버린 이유: 셋 다 찍을 돈이 없다. S2 의 72문항
#     결과가 이미 세 모델을 덮고 있으므로, 250문항 확장은 제일 센 모델 하나면 된다.
#   - x50b 에 astra 를 넣은 이유: astra 는 본 캡처 데이터가 0 이다(선별 24문항뿐).
#     그 선별에서 max/low 배수 중앙이 4.7배로 sol(3.4) · terra(3.5)보다 컸다.
#     "A1 순위가 추론토큰 격차 순위와 거의 같다"는 관찰대로면 astra 가 제일 잘
#     샐 수 있다. 단가 1등이 탐지도 1등이면 그 자체가 결과다. 250문항 풀캡처는
#     $9.06 이라 못 넣지만 50문항(250콜)은 $1.82 다. 덤으로 S9 가 원래 목적
#     (네 모델을 같은 50문항으로 연속 캡처해 Task C 의 '모델마다 캡처 시각이
#     다르다' 교란 제거)을 비로소 채운다. 3모델이면 반쪽이다.
#     한계는 분명하다 — 50문항은 Task A 엔 얇다. 목적은 Task C 교차다.
#
# 2026-11-22 사고 — 왜 크레딧이 $12.74 밖에 안 남았는가
#   watch_cut_s4.sh 를 A안(MARGIN=1.5)과 B안(MARGIN=3.0)으로 두 번 띄웠다.
#   18초 간격으로 둘 다 발동해 f250_sol 과 f250_terra 가 1시간 반 동시에 돌았다.
#   두 tcpdump 필터가 같아서(OpenAI 는 Cloudflare 뒤라 모델이 달라도 같은 IP)
#   서로의 패킷을 같이 잡았고, 양쪽 pcap 의 타이밍 피처가 전부 망가졌다. $7.47 소실.
#   (B 의 pkill 패턴 'run_openai_next\.sh' 는 'run_openai_next_b.sh' 를 못 잡는다.
#    그래서 A 의 러너가 살아남아 다음 단계로 넘어갔다.)
#   막는 장치를 두 겹 넣었다.
#     1) 이 스크립트의 flock — 런처가 두 번 뜨는 것 자체를 막는다.
#     2) run_openai_next.sh 의 stage() 안 pgrep 검사 — 캡처를 띄우기 직전에
#        다른 캡처가 있으면 전체를 멈춘다. 런처가 어떻게 뜨든 동시 캡처는 못 난다.
#   토큰 로그는 멀쩡해서 단가는 실측으로 확정됐다:
#     f250_sol $0.01532/콜 ($19.15/1250콜) · f250_terra $0.00920/콜 ($11.50/1250콜)
#
# 예산 가드 (예상)
#   BUDGET = 12.74 - 1.2(여유) = $11.54
#     f250_sol  상한 8.5  → 누적 8.50   (상한에서 잘린다)
#     x50b_luna  0.1 → 8.54   x50b_terra 0.5 → 8.85
#     x50b_sol   0.7 → 9.26   x50b_astra 2.2 → 11.08 ≤ 11.54 통과
#   실지출 약 $11.1, 잔액 약 $1.7.
#
# 입력 : ~/.llm_keys (OPENAI_API_KEY), out/qfile_anth250.json, out/qfile_oai_cross50.json
# 출력 : out/openai_strict_<tag>_*.pcap · ..._log.jsonl · out/<tag>.csv
#        out/run_oai_final.out (로그), run_openai_next_c.sh (상한만 바꾼 복사본)
#
# 사용 : nohup bash run_openai_final.sh > out/run_oai_final.out 2>&1 &
#        BALANCE=12.74 bash run_openai_final.sh     # 잔액을 다시 확인했을 때
#        BUDGET=8 bash run_openai_final.sh          # 예산을 직접 줄 때
#
# 작성일: 2026-11-22
set -u
cd "$(dirname "$0")"

BALANCE="${BALANCE:-12.74}"
MARGIN="${MARGIN:-1.2}"
LOCK="${LOCK:-out/.openai_capture.lock}"

say() { echo "[$(date +%F' '%H:%M:%S)] $*"; }

# ── 0. 락. 런처가 두 번 뜨는 것을 막는다 ───────────────────────────
# fd 9 는 exec 를 건너 그대로 상속되므로, 이 락은 아래 exec 로 띄우는 러너가
# 끝날 때까지 유지된다. 두 번째 런처는 여기서 즉시 멈춘다.
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[중단] 이미 다른 캡처 런처가 락($LOCK)을 쥐고 있다. 아무것도 안 돌린다."
  echo "       누가 쥐고 있는지:  fuser -v $LOCK   또는  pgrep -af run_openai"
  exit 1
fi

# ── 1. 앞선 캡처가 남아 있으면 돌지 않는다 ─────────────────────────
# 락은 이 스크립트를 거쳐 뜬 것만 막는다. 손으로 띄운 러너는 락을 안 쥔다.
if pgrep -f 'openai_capture_run_strict\.py|run_openai_next' > /dev/null; then
  echo "[중단] 아직 캡처가 돌고 있다. 먼저 끝내거나 정리하라."
  pgrep -af 'openai_capture_run_strict\.py|run_openai_next' | sed 's/^/    /'
  exit 1
fi

# ── 2. 예산 ────────────────────────────────────────────────────────
if [ -z "${BUDGET:-}" ]; then
  BUDGET=$(awk "BEGIN{printf \"%.2f\", $BALANCE - $MARGIN}")
  say "예산: 잔액 \$$BALANCE - 여유 \$$MARGIN = \$$BUDGET"
fi
if awk "BEGIN{exit !($BUDGET < 1)}"; then
  say "[중단] 예산이 \$$BUDGET 다. 돌릴 단계가 없다."
  exit 1
fi

# ── 3. 상한을 바꾼 복사본 ──────────────────────────────────────────
# 돌고 있는 스크립트를 제자리에서 고치면 bash 가 바이트 오프셋으로 되읽다가 깨진다.
# 원본은 건드리지 않고 복사본에서 상한만 바꾼다.
cp run_openai_next.sh run_openai_next_c.sh

# S8: sol 상한만 14.0 → 8.5 로 내린다.
# terra·luna 는 줄을 지우지 않는다. 지우려면 줄끝 백슬래시까지 손봐야 해서
# for 문이 깨지기 쉽다(2026-11-22 에 실제로 깨뜨렸다). 대신 **아래 4단계에서
# S8 을 ONLY=sol 로 따로 띄운다** — `only "$NICK" || continue` 가 그 일을 한다.
sed -i 's#"gpt-6\.1-sol|2|10|14\.0|sol"#"gpt-6.1-sol|2|10|8.5|sol"#'  run_openai_next_c.sh

# S9: 실측 단가(arm 0, 250콜)에 맞게 조인다. luna $0.04 · terra $0.31 · sol $0.41 · astra $1.82.
# S1 의 x50_* 과 줄이 똑같으므로 반드시 'x50b' 가 든 줄 다음에만 바꾼다.
sed -i '/x50b_luna/,+1  s/--max-spend 0\.3$/--max-spend 0.1/' run_openai_next_c.sh
sed -i '/x50b_terra/,+1 s/--max-spend 1\.0$/--max-spend 0.5/' run_openai_next_c.sh
sed -i '/x50b_sol/,+1   s/--max-spend 1\.2$/--max-spend 0.7/' run_openai_next_c.sh
sed -i '/x50b_astra/,+1 s/--max-spend 2\.6$/--max-spend 2.2/' run_openai_next_c.sh

if ! bash -n run_openai_next_c.sh; then
  say "[중단] 복사본 문법 오류. 아무것도 안 돌린다."
  exit 1
fi

# 바뀐 게 맞는지 눈으로 확인할 수 있게 찍는다.
say "S8 sol 상한:"
grep 'gpt-6\.1-sol|2|10|8\.5|sol' run_openai_next_c.sh | sed 's/^/    /'
say "S9 상한:"
grep -A1 'x50b_' run_openai_next_c.sh | grep 'max-spend' | sed 's/^/    /'

# ── 4. 기동 ────────────────────────────────────────────────────────
# 두 번에 나눠 띄운다. ONLY 가 전역이라 한 번에 못 하기 때문이다.
#   S8 은 sol 만 원하고, S9 는 네 모델을 다 원한다.
#   `only "$NICK" || continue` 가 ONLY 에 없는 모델을 걸러준다.
# BUDGET 은 호출마다 새로 세므로, 두 번째 호출에는 첫 번째가 쓴 만큼을 빼고 준다.
LOG1="out/.final_s8.log"

say "1/2 — S8 f250_sol (ONLY=sol, 예산 \$8.6)"
env BUDGET=8.6 ONLY="sol" bash run_openai_next_c.sh 8 2>&1 | tee "$LOG1"

SPENT1=$(sed -n 's/.*누적 \$\([0-9.]*\) \/.*/\1/p' "$LOG1" | tail -1)
[ -z "$SPENT1" ] && SPENT1=8.6 && say "[경고] S8 실비를 못 읽었다. 최악값 \$8.6 으로 본다."
rm -f "$LOG1"

BUDGET2=$(awk "BEGIN{printf \"%.2f\", $BUDGET - $SPENT1}")
say "S8 실비 \$$SPENT1 → S9 예산 \$$BUDGET2"
if awk "BEGIN{exit !($BUDGET2 < 0.2)}"; then
  say "[중단] S9 를 돌릴 예산이 \$$BUDGET2 다. 여기서 끝낸다."
  exit 0
fi

# ONLY 에 astra 를 넣어야 S9 의 astra 단계가 돈다(only() 기본값엔 astra 가 없다).
say "2/2 — S9 x50b 네 모델 (예산 \$$BUDGET2)"
exec env BUDGET="$BUDGET2" ONLY="luna terra sol astra" bash run_openai_next_c.sh 9
