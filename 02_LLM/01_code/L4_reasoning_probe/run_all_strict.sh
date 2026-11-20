#!/usr/bin/env bash
# run_all_strict.sh — Gemini / Anthropic / OpenAI 본 캡처를 한 번에, 그러나 차례로 돌린다.
#
# 왜 차례로인가
#   동시에 돌리면 같은 회선을 나눠 쓰게 되어 패킷 간격(IAT)·TTFT 가 서로 오염된다.
#   타이밍이 핵심 피처이므로 병렬은 데이터를 버리는 짓이다. 대신 사람이 중간에
#   붙어 있을 필요가 없게 전 단계를 하나의 스크립트로 묶는다.
#
# 입력 : ~/.llm_keys (GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY)
#        out/qfile_gemini_rest260.json, out/qfile_opus_rest.json, out/qfile_anth250.json
# 출력 : 단계마다 out/<provider>_strict_<tag>_<ts>.pcap, ..._log.jsonl, out/<tag>.csv
#        진행 상황은 out/run_all_<ts>.out
#
# 사용 : bash run_all_strict.sh            # 전부
#        bash run_all_strict.sh 3 4        # 3,4 단계만
#
# 주의 : 전 단계 합이 약 5,600 콜이다. 콜당 대기까지 치면 하루를 넘길 수 있다.
#        중간에 끊겨도 각 단계는 독립이고, 블록 셔플이라 찍힌 문항은 조건이 다 모인다.
# 작성일: 2026-11-19
set -u
cd "$(dirname "$0")"
TS=$(date +%Y%m%d_%H%M%S)
LOCAL_IP="${LOCAL_IP:-163.152.223.17}"

# 키를 셸에 올린다. 없으면 한 단계도 돌 수 없으니 먼저 죽인다.
[ -f "$HOME/.llm_keys" ] && . "$HOME/.llm_keys"
for v in GEMINI_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY; do
  eval "x=\${$v:-}"; [ -z "$x" ] && echo "[경고] $v 없음 — 해당 단계는 실패한다."
done

# 캡처 한 단계를 돌리고, 방금 생긴 pcap 을 CSV 까지 파싱한다.
#   $1 래퍼 스크립트  $2 pcap 접두어  $3 태그  $4.. 러너 인자
stage() {
  local sh="$1" prefix="$2" tag="$3"; shift 3
  echo; echo "=================================================="
  echo "[$(date +%H:%M:%S)] 시작: $tag  ($sh)"
  echo "=================================================="
  if bash "$sh" "$tag" "$@"; then
    # 태그가 같은 pcap 중 가장 최근 것. 래퍼가 타임스탬프를 붙이므로 glob 으로 찾는다.
    local pcap
    pcap=$(ls -t out/${prefix}_strict_${tag}_*.pcap 2>/dev/null | head -1)
    if [ -n "$pcap" ]; then
      echo "[$(date +%H:%M:%S)] 파싱: $pcap"
      python3 parse_pcap.py "$pcap" "out/${prefix}_strict_${tag}_log.jsonl" \
        --local-ip "$LOCAL_IP" --out "out/${tag}.csv" || echo "[경고] $tag 파싱 실패"
    else
      echo "[경고] $tag pcap 을 못 찾았다."
    fi
  else
    echo "[실패] $tag 단계가 비정상 종료. 다음 단계로 넘어간다."
  fi
}

want() { [ $# -eq 0 ] && return 0; case " $PICK " in *" $1 "*) return 0;; *) return 1;; esac; }
PICK="${*:-}"

# ── 1. Gemini 잔여분 ───────────────────────────────────────────────
# 무료 등급 일일 할당량에 걸려 771문항 중 260문항이 조건 미완으로 남았다.
# --skip-done 으로 이미 성공한 칸은 건너뛰므로 실제 콜은 약 395개 — 하루 몫 안에 든다.
want 1 && stage capture_strict.sh gem v2rest9 \
  --qset v2 --qfile out/qfile_gemini_rest260.json \
  --efforts low,medium,high --repeats 1 --sleep 4 --block-shuffle \
  --skip-done "$(ls out/gem_strict_v2rest*_log.jsonl | tr '\n' ',')"

# ── 2. Anthropic opus 잔여분 ───────────────────────────────────────
# 예산 가드가 1047/1250 에서 끊어 41문항이 미완이다. 205콜.
want 2 && stage anthropic_capture_strict.sh anthropic opus_rest \
  --model claude-opus-5-5 --qset v2 --qfile out/qfile_opus_rest.json \
  --efforts low,medium,high,xhigh,max --repeats 1 --sleep 3 \
  --block-shuffle --price-in 4 --price-out 20 --max-spend 4.0

# ── 3. Anthropic sonnet ────────────────────────────────────────────
# haiku·opus 와 같은 250문항. 세 번째 Claude 모델이라 Task C 의 모델간 비교가 생긴다.
# 단가가 opus 의 절반($2/$10)이라 전량 약 $8 예상. 가드는 넉넉히 12.
want 3 && stage anthropic_capture_strict.sh anthropic sonnet250 \
  --model claude-sonnet-5-5 --qset v2 --qfile out/qfile_anth250.json \
  --efforts low,medium,high,xhigh,max --repeats 1 --sleep 3 \
  --block-shuffle --price-in 2 --price-out 10 --max-spend 12.0

# ── 4~6. OpenAI 3모델 ──────────────────────────────────────────────
# Claude 와 같은 250문항·같은 5단계. responses API 를 쓴다(추론토큰 usage 가 여기만 나온다).
# 단가가 20배 차이나므로 모델마다 가드를 따로 건다.
want 4 && stage openai_capture_strict.sh openai luna250 \
  --model gpt-6-luna --qset v2 --qfile out/qfile_anth250.json \
  --efforts low,medium,high,xhigh,max --repeats 1 --sleep 3 \
  --block-shuffle --api responses --price-in 0.10 --price-out 0.50 --max-spend 2.0

want 5 && stage openai_capture_strict.sh openai terra250 \
  --model gpt-6.1-terra --qset v2 --qfile out/qfile_anth250.json \
  --efforts low,medium,high,xhigh,max --repeats 1 --sleep 3 \
  --block-shuffle --api responses --price-in 1 --price-out 5 --max-spend 8.0

want 6 && stage openai_capture_strict.sh openai sol250 \
  --model gpt-6.1-sol --qset v2 --qfile out/qfile_anth250.json \
  --efforts low,medium,high,xhigh,max --repeats 1 --sleep 3 \
  --block-shuffle --api responses --price-in 2 --price-out 10 --max-spend 14.0

echo; echo "[$(date +%H:%M:%S)] 전체 종료."
