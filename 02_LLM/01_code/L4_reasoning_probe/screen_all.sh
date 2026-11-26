#!/usr/bin/env bash
# screen_all.sh — 본캡처 전 전수 검증 + 문항 선별을 한 번에 돌린다.
#
# 왜 이 순서인가
#   본캡처는 수백 콜이고 astra 는 출력 단가가 $50/1M 이다. 문항이 쉬우면 추론이
#   안 일어나 라벨과 신호가 대응하지 않고, 어려우면 작은 모델이 토큰 한계까지 가
#   답을 못 낸다(Groq 1차 q4 에서 4콜 손실). 둘 다 캡처를 통째로 버리게 만든다.
#   그래서 (0) 문법 → (1) 연결 스모크 → (2) 전 provider 선별 → (3) 교집합 순으로
#   값싼 검증부터 깔고, 마지막에만 돈 드는 캡처로 넘어간다.
#
# 사용:
#   bash screen_all.sh check          # 0단계만: 문법·import 검사 (API 콜 없음, 무료)
#   bash screen_all.sh smoke          # 1단계: provider 당 2문항 (콜 수십 개, 몇 센트)
#   bash screen_all.sh hard           # 2단계: hard 세트 전수 선별
#   bash screen_all.sh base           # 2단계: base 세트 전수 선별(경계 근거용)
#   bash screen_all.sh combine hard   # 3단계: 교집합 산출
#
# 필요 환경변수: OPENAI_API_KEY / GEMINI_API_KEY / GROQ_API_KEY
#   없는 provider 는 건너뛰고 경고만 남긴다(전체를 멈추지 않는다).
# 출력: out/screen_<provider>_<model>_<qset>.json  +  out/screen_<stage>.log
# 작성일: 2026-11-06
set -u
cd "$(dirname "$0")"
mkdir -p out

STAGE="${1:-check}"
QSET="${2:-hard}"

# 선별 대상. OpenAI 는 티어 4개를 전부 넣는다 — astra 포함.
#   astra 는 단가가 가장 높지만(출력 $50/1M) 선별은 문항당 설정 수 만큼의 1콜씩이라
#   30문항 x 6설정 = 180콜, 전체 토큰이 콜당 200 안팎이라 $2 미만이다. 빼지 않는다.
OPENAI_MODELS=(gpt-6-luna gpt-6.1-terra gpt-6-sol gpt-6-astra)
GEMINI_MODELS=(gemini-3.5-flash-lite)
GROQ_MODELS=(openai/gpt-oss-20b openai/gpt-oss-120b)

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── 0단계: 문법·import 검사 ───────────────────────────────────────────────
# API 를 치기 전에 깨진 코드를 먼저 잡는다. 여기서 한 번 걸러두면 선별 도중
# 수십 콜을 쓴 뒤 NameError 로 멈추는 일이 없다.
stage_check() {
  log "문법 검사"
  local files=(screen_qset.py questions_hard.py openai_capture_run_strict.py
               groq_capture_run_strict.py capture_run_strict.py probe_usage.py)
  local fail=0
  for f in "${files[@]}"; do
    if [ ! -f "$f" ]; then echo "  없음: $f"; fail=1; continue; fi
    if python3 -m py_compile "$f" 2>/tmp/pyc.err; then
      echo "  OK   $f"
    else
      echo "  FAIL $f"; sed 's/^/       /' /tmp/pyc.err; fail=1
    fi
  done

  log "import 검사 (SDK 설치 여부 포함)"
  python3 - <<'PY'
import importlib, sys
mods = {"openai": "pip install openai", "groq": "pip install groq",
        "google.genai": "pip install google-genai"}
miss = []
for m, how in mods.items():
    try:
        importlib.import_module(m)
        print(f"  OK   {m}")
    except Exception as e:
        print(f"  없음 {m}  ({type(e).__name__}) -> {how}")
        miss.append(m)
try:
    import screen_qset
    print(f"  OK   screen_qset  (base {len(screen_qset.QSETS['base'])}문항 / "
          f"hard {len(screen_qset.QSETS['hard'])}문항)")
except Exception as e:
    print(f"  FAIL screen_qset: {type(e).__name__}: {e}")
    sys.exit(1)
PY
  local rc=$?

  log "키 확인"
  for v in OPENAI_API_KEY GEMINI_API_KEY GOOGLE_API_KEY GROQ_API_KEY; do
    if [ -n "${!v:-}" ]; then echo "  있음 $v"; else echo "  없음 $v"; fi
  done
  [ $fail -eq 0 ] && [ $rc -eq 0 ] && log "0단계 통과" || { log "0단계 실패"; return 1; }
}

# ── 공통: provider 하나 선별 ──────────────────────────────────────────────
run_one() {
  local prov="$1" model="$2" qset="$3" limit="$4"
  local extra=""
  [ "$limit" != "0" ] && extra="--limit $limit"
  log "선별 $prov / $model / $qset ${limit:+(앞 $limit문항)}"
  # 실패해도 다음 provider 로 넘어간다. 키가 없거나 모델이 막혀도 전체가 멈추면 안 된다.
  python3 screen_qset.py --provider "$prov" --model "$model" --qset "$qset" \
      $extra 2>&1 | tee -a "out/screen_${qset}.log" || log "  실패: $prov/$model (계속)"
}

stage_run() {
  local qset="$1" limit="$2"
  : > "out/screen_${qset}.log"
  if [ -n "${OPENAI_API_KEY:-}" ]; then
    for m in "${OPENAI_MODELS[@]}"; do run_one openai "$m" "$qset" "$limit"; done
  else log "OPENAI_API_KEY 없음 — 건너뜀"; fi
  if [ -n "${GEMINI_API_KEY:-}${GOOGLE_API_KEY:-}" ]; then
    for m in "${GEMINI_MODELS[@]}"; do run_one gemini "$m" "$qset" "$limit"; done
  else log "GEMINI_API_KEY 없음 — 건너뜀"; fi
  if [ -n "${GROQ_API_KEY:-}" ]; then
    for m in "${GROQ_MODELS[@]}"; do run_one groq "$m" "$qset" "$limit"; done
  else log "GROQ_API_KEY 없음 — 건너뜀"; fi
  log "로그 -> out/screen_${qset}.log"
}

case "$STAGE" in
  check)   stage_check ;;
  smoke)   stage_check && stage_run "$QSET" 2 ;;
  hard)    stage_check && stage_run hard 0 ;;
  base)    stage_check && stage_run base 0 ;;
  combine) python3 screen_qset.py --combine "out/screen_*_${QSET}.json" ;;
  *) echo "사용: bash screen_all.sh {check|smoke|hard|base|combine} [qset]"; exit 1 ;;
esac
