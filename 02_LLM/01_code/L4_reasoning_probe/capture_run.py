"""
capture_run.py — Phase 1: 패킷캡처와 동기화된 Gemini 요청 생성기.

목적: gemini_probe와 같은 3조건(no_think/low/high) 요청을 보내되, 각 요청의
      **벽시계 시각(time.time)**을 JSONL 로그로 남긴다. 이 로그로 나중에 pcap을
      요청 구간별로 잘라 라벨링한다(parse_pcap.py). 앱타이밍 지표도 함께 기록해
      '앱 vs 패킷' 비교가 가능하게 한다.

사용: capture.sh 가 tcpdump와 함께 이 스크립트를 호출한다(직접도 가능).
  python3 capture_run.py --repeats 3 --log out/capture_log.jsonl
입력: GEMINI_API_KEY. 출력: out/capture_log.jsonl (요청별 시각·조건·앱지표)
작성일: 2026-09-01
"""
import os
import json
import time
import argparse
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash-lite"
QUESTIONS = [
    "다음 논리 퍼즐: A>B>C>D 이고 D>A면 모순이 있는가? 결론만 한 문장.",
    "17 x 23은? 답만.",
    "1부터 100까지 정수 중 3의 배수도 5의 배수도 아닌 수의 개수는? 답만.",
    "'배는 과일이자 탈것이자 신체부위다'가 왜 중의적인지 한 문장.",
    "체스에서 나이트가 a1에서 h8까지 최소 몇 번 이동으로 갈 수 있나? 답만.",
    "물이 100도에서 끓는 이유를 한 문장.",
    "수열의 다음 항: 2, 6, 12, 20, 30, ? 답만.",
    "'닭이 먼저냐 달걀이 먼저냐'에 진화론적으로 한 문장.",
]
CONDITIONS = [
    ("no_think",   None),
    ("think_low",  {"thinking_level": "low"}),
    ("think_high", {"thinking_level": "high"}),
]


def run_one(client, question, think):
    """스트리밍 요청. 벽시계 시각(t_start/t_first_answer/t_end)과 앱지표 반환."""
    cfg = None if not think else types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(**think))
    t_start = time.time()             # 벽시계(pcap과 정렬용)
    t_first_answer = None
    answer_chars = 0
    thoughts_tok = None
    answer_tok = None
    stream = client.models.generate_content_stream(
        model=MODEL, contents=question, config=cfg)
    for chunk in stream:
        t = time.time()
        cand = (getattr(chunk, "candidates", None) or [None])[0]
        content = getattr(cand, "content", None) if cand else None
        for part in (getattr(content, "parts", None) or []):
            txt = getattr(part, "text", None)
            if txt and not getattr(part, "thought", False):
                if t_first_answer is None:
                    t_first_answer = t
                answer_chars += len(txt)
        um = getattr(chunk, "usage_metadata", None)
        if um is not None:
            thoughts_tok = getattr(um, "thoughts_token_count", None) or thoughts_tok
            answer_tok = getattr(um, "candidates_token_count", None) or answer_tok
    t_end = time.time()
    return {
        "t_start": t_start, "t_first_answer": t_first_answer, "t_end": t_end,
        "app_ttft_ms": round((t_first_answer - t_start) * 1000, 1) if t_first_answer else None,
        "app_total_ms": round((t_end - t_start) * 1000, 1),
        "answer_chars": answer_chars,
        "thoughts_tokens": thoughts_tok, "output_tokens": answer_tok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=4.0, help="요청 간 간격(패킷 구간 분리 위해 넉넉히)")
    ap.add_argument("--log", default="out/capture_log.jsonl")
    args = ap.parse_args()

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY 없음")
    client = genai.Client(api_key=key)
    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS

    logp = Path(args.log)
    logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(qs) * len(CONDITIONS) * args.repeats
    i = 0
    time.sleep(1.0)   # tcpdump 워밍업 여유
    with open(logp, "w", encoding="utf-8") as f:
        for qi, q in enumerate(qs):
            for cond, think in CONDITIONS:
                for rep in range(args.repeats):
                    i += 1
                    try:
                        m = run_one(client, q, think)
                        m["error"] = None
                    except Exception as e:
                        m = {"error": f"{type(e).__name__}: {e}"}
                    m.update({"idx": i, "q_idx": qi, "condition": cond, "rep": rep})
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
                    f.flush()
                    tag = m.get("error") or f"app_ttft={m.get('app_ttft_ms')}ms think_tok={m.get('thoughts_tokens')}"
                    print(f"[{i}/{total}] q{qi} {cond:10s} {tag}")
                    time.sleep(args.sleep)
    print(f"\n[done] 로그 -> {logp}")


if __name__ == "__main__":
    main()
