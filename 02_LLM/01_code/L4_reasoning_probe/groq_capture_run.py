"""
groq_capture_run.py — E3: Groq API로 추론 on/off 요청 생성(패킷캡처 동기용).

목적: 서비스 일반화(E3) 위해 2번째 서비스(Groq) 데이터 수집. Gemini와 동일하게
      추론 heavy/light 조건으로 요청하고 벽시계 시각을 로그로 남긴다.
      추론 on/off는 '모델 선택'으로: deepseek-r1(추론) vs llama(비추론).
준비: pip install groq ; export GROQ_API_KEY=gsk_...
사용: groq_capture.sh 가 tcpdump와 함께 호출. 출력: out/groq_log.jsonl
비고: Groq 모델명은 바뀔 수 있어 --list로 확인 가능. reasoning 파싱은 방어적.
작성일: 2026-09-02
"""
import os
import json
import time
import argparse
from pathlib import Path

from groq import Groq

# gpt-oss = 추론모델, reasoning_effort로 low/high 조절(Gemini thinking_level과 대응).
# → 크로스서비스 비교 깔끔(둘 다 한 모델서 low/high).
MODEL = "openai/gpt-oss-20b"
# 3조건(low/med/high)으로 Gemini와 총합(72) 맞춤 + 깊이 그라데이션.
# gpt-oss가 "medium" 안 받으면 그 조건만 에러 → low/high로 되돌리면 됨.
CONDITIONS = [
    ("think_low",  "low"),
    ("think_med",  "medium"),
    ("think_high", "high"),
]
QUESTIONS = [
    "17 x 23은? 답만.", "프랑스의 수도는? 답만.", "물이 어는 온도는? 답만.",
    "다음 논리 퍼즐: A>B>C>D 이고 D>A면 모순인가? 결론만.",
    "체스에서 나이트가 a1에서 h8까지 최소 몇 번? 답만.",
    "1~100 중 3의 배수도 5의 배수도 아닌 수 개수? 답만.",
    "수열 2,6,12,20,30 다음 항? 답만.", "24를 소인수분해하면? 답만.",
]


def run_one(client, question, effort):
    """스트리밍 요청. 벽시계 t_start/t_first_answer/t_end + 토큰수 반환.

    reasoning_effort=low/high 로 추론 깊이 조절, reasoning_format='hidden'으로
    추론을 스트림에 안 실음 → 요청 후 '침묵' 뒤 답(pkt_gap 신호). Gemini와 동일 구조.
    """
    t0 = time.time(); t_first = None; in_think = False; saw_think = False
    answer_chars = 0; comp_tok = None
    stream = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": question}],
        stream=True, temperature=0.6,
        reasoning_effort=effort, reasoning_format="hidden",
    )
    for chunk in stream:
        t = time.time()
        ch = (chunk.choices or [None])[0]
        delta = getattr(ch, "delta", None) if ch else None
        txt = getattr(delta, "content", None) if delta else None
        # 일부 SDK는 reasoning을 delta.reasoning으로 분리.
        reasoning = getattr(delta, "reasoning", None) if delta else None
        if reasoning:
            saw_think = True
        if txt:
            # <think> 태그로 추론 구간 근사 판별.
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
        u = getattr(chunk, "usage", None)
        if u is not None:
            comp_tok = getattr(u, "completion_tokens", None) or comp_tok
    t_end = time.time()
    return {"t_start": t0, "t_first_answer": t_first, "t_end": t_end,
            "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
            "app_total_ms": round((t_end - t0) * 1000, 1),
            "answer_chars": answer_chars, "output_tokens": comp_tok,
            "had_reasoning": saw_think}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--log", default="out/groq_log.jsonl")
    ap.add_argument("--model", default=None, help="모델 override (예: openai/gpt-oss-120b)")
    ap.add_argument("--list", action="store_true", help="사용가능 모델 출력 후 종료")
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
    logp = Path(args.log); logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(qs) * len(CONDITIONS) * args.repeats; i = 0
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for qi, q in enumerate(qs):
            for cond, effort in CONDITIONS:
                for rep in range(args.repeats):
                    i += 1
                    try:
                        m = run_one(client, q, effort); m["error"] = None
                    except Exception as e:
                        m = {"error": f"{type(e).__name__}: {e}"}
                    m.update({"idx": i, "q_idx": qi, "condition": cond,
                              "service": "groq", "model": MODEL, "effort": effort, "rep": rep})
                    f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
                    tag = m.get("error") or f"ttft={m.get('app_ttft_ms')}ms out={m.get('output_tokens')} reason={m.get('had_reasoning')}"
                    print(f"[{i}/{total}] q{qi} {cond:10s} {tag}")
                    time.sleep(args.sleep)
    print(f"\n[done] -> {logp}")


if __name__ == "__main__":
    main()
