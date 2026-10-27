"""
gemini_probe.py — L4 초미니 검증 (Gemini 무료 API 버전).

목적: mini_probe.py와 동일 실험을 Gemini로. thinking_budget으로 추론 ON/OFF·깊이를
      조절하고, 스트리밍 청크 도착 시각으로 "요청→첫 답변까지 지연(ttft_answer)"과
      전체 시간을 잰다. Google AI Studio 무료 티어(결제 불필요).

준비:
  pip install google-genai
  export GEMINI_API_KEY="..."   # aistudio.google.com/apikey 에서 무료 발급
입력: 없음(아래 상수). 출력: out/probe_results_gemini.csv
비고: google-genai SDK 구조가 버전따라 조금 다를 수 있어 방어적으로 파싱한다.
작성일: 2026-09-01
"""

import os
import csv
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

from google import genai
from google.genai import types

# 한 모델에서 비추론/얕은추론/깊은추론을 다 돌린다(교차모델 confound 제거).
# gemini-3.5-flash-lite = Gemini 3세대, thinking_level 로 조절.
MODEL = "gemini-3.5-flash-lite"

QUESTIONS = [
    "다음 논리 퍼즐을 풀어줘: A는 B보다 크고, B는 C보다 크며, C는 D보다 크다. 그리고 D는 A보다 크다면 모순이 있는가? 결론만 한 문장.",
    "17 x 23을 답만.",
    "1부터 100까지 정수 중 3의 배수도 5의 배수도 아닌 수의 개수는? 답만.",
    "'배는 과일이자 탈것이자 신체부위다'가 왜 중의적인지 한 문장.",
    "체스에서 나이트가 a1에서 h8까지 최소 몇 번 이동으로 갈 수 있나? 답만.",
    "물이 100도에서 끓는 이유를 한 문장.",
    "수열의 다음 항: 2, 6, 12, 20, 30, ? 답만.",
    "'닭이 먼저냐 달걀이 먼저냐'에 진화론적으로 한 문장.",
]

# 조건: (라벨, thinking_config kwargs 또는 None).
#  - no_think   : thinking 설정 없음 = 기본 OFF (진짜 비추론 baseline)
#  - think_low  : thinking_budget 512  (얕은 추론)
#  - think_high : thinking_budget 4096 (깊은 추론)
# 전부 같은 모델(MODEL) → "비추론 vs 짧은추론 vs 깊은추론" 3단, confound 없음.
CONDITIONS = [
    ("no_think",   None),
    ("think_low",  {"thinking_level": "low"}),
    ("think_high", {"thinking_level": "high"}),
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_one(client, question, think):
    """한 요청을 스트리밍하며 청크 시각 기록. 핵심=ttft_answer_ms(요청→첫 답변).

    think=None 이면 비추론(thinking_config 없이). 아니면 dict(예:{"thinking_budget":512}).
    생각은 '조용한 지연'으로 흐른다(요청→첫 답변까지 침묵 = 추론 지연 신호).
    생각 토큰량은 usage_metadata.thoughts_token_count로.
    """
    t0 = time.perf_counter()
    t_first_chunk = None
    t_first_answer = None    # 첫 '답변' 텍스트 ← 핵심(그 앞 침묵=추론 지연)
    t_first_thought = None
    t_end = None
    n_thought_chunks = 0
    n_answer_chunks = 0
    answer_chars = 0
    thoughts_tok = None
    answer_tok = None

    if not think:
        cfg = None                      # 비추론 = thinking 설정 안 함(기본 OFF)
    else:
        cfg = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(**think)   # 예: thinking_budget=512
        )
    stream = client.models.generate_content_stream(
        model=MODEL, contents=question, config=cfg,
    )
    for chunk in stream:
        t = time.perf_counter()
        if t_first_chunk is None:
            t_first_chunk = t
        # 방어적 파싱: candidates→content→parts, part.thought / part.text
        cand = (getattr(chunk, "candidates", None) or [None])[0]
        content = getattr(cand, "content", None) if cand else None
        parts = getattr(content, "parts", None) or []
        for part in parts:
            is_thought = bool(getattr(part, "thought", False))
            txt = getattr(part, "text", None)
            if txt is None:
                continue
            if is_thought:
                if t_first_thought is None:
                    t_first_thought = t
                n_thought_chunks += 1
            else:
                if t_first_answer is None:
                    t_first_answer = t
                n_answer_chunks += 1
                answer_chars += len(txt)
        # usage(마지막 청크에 누적).
        um = getattr(chunk, "usage_metadata", None)
        if um is not None:
            thoughts_tok = getattr(um, "thoughts_token_count", None) or thoughts_tok
            answer_tok = getattr(um, "candidates_token_count", None) or answer_tok
    t_end = time.perf_counter()

    def ms(a, b):
        return round((b - a) * 1000, 1) if (a is not None and b is not None) else None

    return {
        "ttft_answer_ms":  ms(t0, t_first_answer),   # ★ 추론 지연 신호
        "ttft_chunk_ms":   ms(t0, t_first_chunk),
        "ttft_thought_ms": ms(t0, t_first_thought),
        "think_dur_ms":    ms(t_first_thought, t_first_answer),
        "total_ms":        ms(t0, t_end),
        "n_thought_chunks": n_thought_chunks,
        "n_answer_chunks":  n_answer_chunks,
        "answer_chars":    answer_chars,
        "thoughts_tokens": thoughts_tok,
        "output_tokens":   answer_tok,
    }


def main():
    ap = argparse.ArgumentParser(description="L4 reasoning probe (Gemini free)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=4.0, help="무료티어 RPM 여유(초)")
    ap.add_argument("--out", default="out/probe_results_gemini.csv")
    args = ap.parse_args()

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY 없음 — aistudio.google.com/apikey 에서 무료 발급 후 export")
    client = genai.Client(api_key=key)

    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS
    rows = []
    total = len(qs) * len(CONDITIONS) * args.repeats
    i = 0
    for qi, q in enumerate(qs):
        for cond, think in CONDITIONS:
            for rep in range(args.repeats):
                i += 1
                try:
                    m = run_one(client, q, think)
                except Exception as e:
                    m = {"error": f"{type(e).__name__}: {e}"}
                m.update({"ts": now_iso(), "q_idx": qi, "condition": cond,
                          "model": MODEL, "think": str(think), "rep": rep,
                          "question": q[:50]})
                rows.append(m)
                if m.get("error"):
                    print(f"[{i}/{total}] q{qi} {cond:8s} ERROR: {m['error']}")
                else:
                    print(f"[{i}/{total}] q{qi} {cond:8s} "
                          f"ttft_answer={m.get('ttft_answer_ms')}ms "
                          f"total={m.get('total_ms')}ms "
                          f"think_tok={m.get('thoughts_tokens')} out={m.get('output_tokens')}")
                time.sleep(args.sleep)

    cols = ["ts", "q_idx", "condition", "model", "think", "rep",
            "ttft_answer_ms", "ttft_chunk_ms", "ttft_thought_ms", "think_dur_ms",
            "total_ms", "n_thought_chunks", "n_answer_chunks", "answer_chars",
            "thoughts_tokens", "output_tokens", "question", "error"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(out)
    print(f"\n[done] {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
