"""
groq_capture_run_strict.py — 길이 완전통제판 캡처 요청 생성기(Groq / gpt-oss).

목적: capture_run_strict.py(Gemini)의 Groq 짝. 모든 조건서 출력을 '한 글자(A/B/C/D)'로
      강제해 출력 길이를 완전히 고정한다. Gemini strict 와 동일한 객관식 문항·단답강제를 써서
      두 서비스를 같은 조건으로 비교한다.
      추론깊이 = gpt-oss reasoning_effort low/medium/high (Gemini thinking_level 에 대응).
      reasoning_format='hidden' 으로 추론을 답 스트림에 안 실음.

2026-10-02 개정 — 1차 캡처(2026-09-23) 분석에서 드러난 결함 3건을 반영:
  (1) 토큰 한계: q4(체스 나이트) 에서 추론이 폭주해 2048 토큰 한계까지 가고 답을 못 냈다.
      4콜 실패(think_med 1 + think_high 3)로 q4 의 think_high 가 통째로 비었고,
      질문별 교차검증에서 그 회차가 깨졌다.
      → max_completion_tokens 를 명시하고, 답이 비면 truncated 플래그로 표시해 분석서 제외.
  (2) 조건 순서 고정: 질문마다 항상 low -> med -> high 순이라 시간 추세가 조건과 엉켰다.
      실측에서 세션 전반 think_low 905ms -> 후반 497ms 로 워밍업 효과가 있었다.
      → 전체 시행을 섞어서 돌리고 실행 순서를 로그에 남긴다.
  (3) 요청 크기 누출: reasoning_effort 값이 "low"(3) / "medium"(6) / "high"(4) 로 글자수가
      전부 달라 요청 바이트에 설정값이 그대로 남는다(Gemini 보다 심함).
      → 조건별로 프롬프트 끝에 공백을 덧붙여 요청 바이트를 맞춘다(PAD_CHARS).
  그리고 반복 기본값을 3 -> 5 로 올려 표본을 108 -> 180 으로 늘린다.

준비: pip install groq ; export GROQ_API_KEY=gsk_...
사용: groq_capture_strict.sh 가 tcpdump와 함께 호출(직접도 가능).
  python3 groq_capture_run_strict.py --repeats 5 --log out/groq_log_strict.jsonl
입력: GROQ_API_KEY. 출력: out/groq_log_strict.jsonl
비고: 파싱은 parse_pcap.py --out out/groq_strict.csv, 분류는 e1_from_csv.py out/groq_strict.csv.
      gpt-oss 는 'no_think'(추론 완전 off) 모드가 없어 조건은 low/med/high 그라데이션이며,
      이는 이 모델이 제공하는 전 단계다. within-provider 비교는 low vs high 가 핵심.
작성일: 2026-09-23 (개정 2026-10-02)
"""
import os
import json
import time
import random
import argparse
from pathlib import Path

from groq import Groq

MODEL = "openai/gpt-oss-20b"

CONDITIONS = [
    ("think_low",  "low"),
    ("think_med",  "medium"),
    ("think_high", "high"),
]

# reasoning_effort 값의 글자수 차이를 프롬프트 끝 공백으로 상쇄해 요청 바이트를 맞춘다.
#   "low"(3) / "medium"(6) / "high"(4)  →  가장 긴 "medium" 기준으로 보정.
# 재보정법: 캡처 후 CSV 에서 조건별 up_bytes 중앙값이 같은지 확인하고 차이만큼 조정.
PAD_CHARS = {"think_low": 3, "think_med": 0, "think_high": 2}

# 추론 폭주 시 한계까지 가서 답이 안 나오는 것을 막지는 못하지만, 명시해두고 플래그로 걸러낸다.
MAX_COMPLETION_TOKENS = 2048

QUESTIONS = [
    "17 x 23 = ? A) 291 B) 391 C) 401 D) 411",
    "1~100 정수 중 3의 배수도 5의 배수도 아닌 수의 개수는? A) 47 B) 53 C) 60 D) 73",
    "수열 2,6,12,20,30 의 다음 항은? A) 40 B) 42 C) 44 D) 46",
    "A>B>C>D 이고 D>A 이면? A) 모순 없음 B) 모순 있음 C) 알 수 없음 D) A=D",
    "체스 나이트가 a1에서 h8까지 가는 최소 이동 수는? A) 4 B) 5 C) 6 D) 7",
    "물이 100도에서 끓는 주된 이유는? A) 중력 B) 증기압=대기압 C) 밀도 D) 표면장력",
    "정십이면체의 면 개수는? A) 8 B) 10 C) 12 D) 20",
    "3 5 8 13 21 다음 피보나치 항은? A) 29 B) 31 C) 34 D) 42",
    "한 변 7인 정사각형 넓이는? A) 14 B) 28 C) 49 D) 56",
    "논리: 모든 A는 B, 어떤 B는 C. 참인가 '어떤 A는 C'? A) 항상참 B) 항상거짓 C) 알수없음 D) 무의미",
    "2진수 1011 의 10진수 값은? A) 9 B) 11 C) 13 D) 15",
    "소수(prime)가 아닌 것은? A) 2 B) 3 C) 9 D) 11",
    "13 x 17 = ? A) 201 B) 211 C) 221 D) 231",
    "2의 10제곱은? A) 512 B) 1024 C) 2048 D) 4096",
    "1부터 20까지 자연수의 합은? A) 190 B) 200 C) 210 D) 220",
    "수열 1,4,9,16,25 의 다음 항은? A) 30 B) 32 C) 36 D) 49",
    "수열 3,7,15,31 의 다음 항은? A) 47 B) 55 C) 63 D) 71",
    "동전 3개를 던져 앞면이 정확히 2개 나오는 경우의 수는? A) 2 B) 3 C) 4 D) 6",
    "주사위 2개의 합이 7이 되는 경우의 수는? A) 4 B) 5 C) 6 D) 7",
    "5명 중 2명을 뽑는 경우의 수는? A) 10 B) 15 C) 20 D) 25",
    "모든 고래는 포유류, 어떤 포유류는 육식. '어떤 고래는 육식'은? A) 항상참 B) 항상거짓 C) 알수없음 D) 무의미",
    "P이면 Q 가 참일 때 Q 가 거짓이면 P 는? A) 참 B) 거짓 C) 알수없음 D) 무관",
    "8진수 17 의 10진수 값은? A) 13 B) 15 C) 17 D) 19",
    "16진수 FF 의 10진수 값은? A) 255 B) 256 C) 15 D) 16",
    "반지름 3인 원의 넓이는? (파이=3.14) A) 18.84 B) 28.26 C) 9.42 D) 37.68",
    "한 변이 4인 정육면체의 부피는? A) 16 B) 48 C) 64 D) 96",
    "물이 어는 온도를 화씨로 하면? A) 0 B) 32 C) 100 D) 212",
    "빛의 속도에 가장 가까운 것은? A) 3만 km/s B) 30만 km/s C) 300만 km/s D) 3천만 km/s",
    "DNA 염기가 아닌 것은? A) 아데닌 B) 구아닌 C) 라이신 D) 시토신",
    "1킬로그램은 몇 그램인가? A) 10 B) 100 C) 1000 D) 10000",
]
# 2026-10-05 추가 — 위 12문항은 1·2차와 비교 가능하도록 순서까지 그대로 두고 18문항을 덧붙였다.
#   늘린 이유: 반복(3->5)을 올려도 질문은 12개뿐이라 '처음 보는 질문에서 되는가'는 좋아지지 않는다.
#   질문별 교차검증에서 독립 표본은 사실상 질문 수이므로, 일반화를 보려면 문항을 늘려야 한다.
#   q4(체스 나이트)처럼 경로 탐색을 요구해 추론이 토큰 한계까지 폭주하는 유형은 새로 넣지 않았다.
INSTR = "\n\n정답 한 글자(A, B, C, D 중 하나)만 출력하라. 설명·다른 말·문장부호 금지."


def _reasoning_tokens(usage):
    """usage에서 추론 토큰수를 방어적으로 추출(gpt-oss/Groq은 위치가 SDK판마다 다름)."""
    if usage is None:
        return None
    for attr in ("reasoning_tokens", "completion_reasoning_tokens"):
        v = getattr(usage, attr, None)
        if v:
            return v
    det = getattr(usage, "completion_tokens_details", None)
    if det is not None:
        v = getattr(det, "reasoning_tokens", None)
        if v:
            return v
        if isinstance(det, dict):
            return det.get("reasoning_tokens")
    return None


def run_one(client, question, effort, pad):
    """스트리밍 요청. 벽시계 t_start/t_first_answer/t_end(pcap 정렬용) + 토큰수 반환."""
    t0 = time.time(); t_first = None; in_think = False; saw_think = False
    answer_chars = 0; comp_tok = None; think_tok = None; finish = None
    # reasoning_format="hidden" 이라 추론 텍스트는 안 와야 정상이다. Gemini 쪽에서
    # 추론량에 비례해 down_bytes 가 커지는 것이 확인됐으므로, Groq 도 같은 일이
    # 벌어지는지 양으로 기록해 둔다(0이면 '바이트 신호 없음'의 직접 근거가 된다).
    reasoning_chars = 0
    # 추론 중 빈 keep-alive 청크가 바이트를 밀어올렸을 가능성을 배제하기 위한 대조.
    chunk_count = 0
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": question + INSTR + (" " * pad)}],
        stream=True, temperature=0.6,
        reasoning_effort=effort, reasoning_format="hidden",
        max_completion_tokens=MAX_COMPLETION_TOKENS,
    )
    for chunk in stream:
        t = time.time()
        chunk_count += 1
        ch = (chunk.choices or [None])[0]
        if ch is not None and getattr(ch, "finish_reason", None):
            finish = ch.finish_reason
        delta = getattr(ch, "delta", None) if ch else None
        txt = getattr(delta, "content", None) if delta else None
        reasoning = getattr(delta, "reasoning", None) if delta else None
        if reasoning:
            saw_think = True
            reasoning_chars += len(reasoning)
        if txt:
            if "<think>" in txt:
                in_think = True; saw_think = True
            if "</think>" in txt:
                in_think = False; saw_think = True
                txt = txt.split("</think>")[-1]
            clean = txt.replace("<think>", "").replace("</think>", "")
            if not in_think and clean.strip():
                if t_first is None:
                    t_first = t
                answer_chars += len(clean)
            elif in_think:
                # <think> 태그 안쪽으로 들어온 추론 텍스트도 바이트로는 내려온 것이다.
                reasoning_chars += len(clean)
        u = getattr(chunk, "usage", None)
        if u is not None:
            comp_tok = getattr(u, "completion_tokens", None) or comp_tok
            think_tok = _reasoning_tokens(u) or think_tok
    t_end = time.time()
    return {"t_start": t0, "t_first_answer": t_first, "t_end": t_end,
            "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
            "app_total_ms": round((t_end - t0) * 1000, 1),
            "answer_chars": answer_chars,
            "thoughts_tokens": think_tok, "output_tokens": comp_tok,
            "had_reasoning": saw_think, "reasoning_chars": reasoning_chars,
            "chunk_count": chunk_count,
            "finish_reason": finish, "pad_chars": pad,
            # 답이 한 글자도 안 나왔으면 추론이 한계까지 간 것(1차서 q4 에 4건 발생).
            "truncated": answer_chars == 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--log", default="out/groq_log_strict.jsonl")
    ap.add_argument("--model", default=None, help="모델 override (예: openai/gpt-oss-120b)")
    ap.add_argument("--list", action="store_true", help="사용가능 모델 출력 후 종료")
    ap.add_argument("--seed", type=int, default=20261002,
                    help="시행 순서 섞기용 시드(재현 가능하게 고정)")
    ap.add_argument("--no-shuffle", action="store_true",
                    help="섞지 않고 예전처럼 순서대로(비교용)")
    args = ap.parse_args()
    global MODEL
    if args.model:
        MODEL = args.model
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise SystemExit("GROQ_API_KEY 없음 — console.groq.com 에서 무료 발급")
    client = Groq(api_key=key)
    if args.list:
        for m in client.models.list().data:
            print(m.id)
        return

    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS
    trials = [(qi, cond, effort, rep)
              for qi, _ in enumerate(qs)
              for cond, effort in CONDITIONS
              for rep in range(args.repeats)]
    if not args.no_shuffle:
        random.Random(args.seed).shuffle(trials)

    logp = Path(args.log); logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(trials)
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for i, (qi, cond, effort, rep) in enumerate(trials, 1):
            try:
                m = run_one(client, qs[qi], effort, PAD_CHARS.get(cond, 0)); m["error"] = None
            except Exception as e:
                m = {"error": f"{type(e).__name__}: {e}"}
            m.update({"idx": i, "order_idx": i, "q_idx": qi, "condition": cond,
                      "service": "groq", "model": MODEL, "effort": effort, "rep": rep,
                      "shuffled": not args.no_shuffle})
            f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
            tag = m.get("error") or (
                f"ttft={m.get('app_ttft_ms')}ms out={m.get('output_tokens')} "
                f"think={m.get('thoughts_tokens')}" + (" [잘림]" if m.get("truncated") else ""))
            print(f"[{i}/{total}] q{qi} {cond:10s} {tag}")
            time.sleep(args.sleep)
    print(f"\n[done] 로그 -> {logp}")
    print("→ 확인 1: answer_chars 가 조건 무관 1로 고정됐는지(길이 통제 성공 여부)")
    print("→ 확인 2: truncated=true 가 몇 건인지(추론 폭주로 답이 없던 콜 — 분석서 제외)")
    print("→ 확인 3: think_tokens 가 low<med<high 로 벌어지는지(추론깊이 설정 반영 여부)")
    print("→ 확인 4: 파싱 후 조건별 up_bytes 중앙값이 같은지(요청 크기 통제 성공 여부)")


if __name__ == "__main__":
    main()
