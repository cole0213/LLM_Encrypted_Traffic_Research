"""
session_run.py — L5 파일럿: 인간형 vs 자율에이전트형 '세션' 트래픽 생성기.

목적: 두 종류의 사용 리듬을 흉내 낸 세션을 Gemini에 던져 tcpdump로 캡처하고,
      세션 단위로 라벨(human/agent)을 남긴다. 나중에 session_classify.py 가
      세션 단위 피처(요청률·gap 통계·추론 밀도)로 human vs agent를 구별한다.
  - human 세션: 턴 적고, 턴 사이 gap 큼(사람이 읽고 치는 시간), 얕은 추론 위주.
  - agent 세션: 턴 많고, gap 거의 0(연속), 깊은 추론 연속(멀티스텝 작업 흉내).

정직: 리듬을 우리가 부과하므로 순환 위험 있음 → 파이프라인·신호 확인용 PoC.
      진짜 에이전트(Claude Code 등) 실측은 다음 단계.
사용: session_capture.sh 가 tcpdump와 함께 호출. (직접도 가능)
출력: out/session_log.jsonl (턴별: session_id·type·시각·thinking)
작성일: 2026-09-02
"""
import os
import json
import time
import random
import argparse
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash-lite"
random.seed(20260902)

# 질문 풀(난이도 섞음). 난이도 편향 줄이려 두 타입 다 여기서 뽑음.
QUESTIONS = [
    "17 x 23은? 답만.", "파리의 수도가 아니라 프랑스의 수도는? 답만.",
    "물이 어는 온도는? 답만.", "'사과'를 영어로? 답만.",
    "다음 논리 퍼즐: A>B>C>D 이고 D>A면 모순인가? 결론만.",
    "체스에서 나이트가 a1에서 h8까지 최소 몇 번? 답만.",
    "1~100 중 3의 배수도 5의 배수도 아닌 수 개수? 답만.",
    "수열 2,6,12,20,30 다음 항? 답만.",
    "24를 소인수분해하면? 답만.", "3x+7=22일 때 x는? 답만.",
]

# 세션 타입: (gap 범위 초, 턴 수 범위, thinking_level)
TYPES = {
    "human": {"gap": (3.0, 14.0), "turns": (5, 8),  "level": "low"},
    "agent": {"gap": (0.1, 0.8),  "turns": (9, 14), "level": "high"},
}
SESSION_GAP = 25.0   # 세션 사이 긴 공백(파싱서 세션 분리용)


def ask(client, q, level):
    """한 요청 스트리밍. 벽시계 t_start/t_first_answer/t_end + 앱지표 반환."""
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level=level))
    t0 = time.time(); t_first = None; thoughts = None; outtok = None
    for chunk in client.models.generate_content_stream(model=MODEL, contents=q, config=cfg):
        t = time.time()
        cand = (getattr(chunk, "candidates", None) or [None])[0]
        content = getattr(cand, "content", None) if cand else None
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "text", None) and not getattr(part, "thought", False):
                if t_first is None:
                    t_first = t
        um = getattr(chunk, "usage_metadata", None)
        if um is not None:
            thoughts = getattr(um, "thoughts_token_count", None) or thoughts
            outtok = getattr(um, "candidates_token_count", None) or outtok
    t_end = time.time()
    return {"t_start": t0, "t_first_answer": t_first, "t_end": t_end,
            "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
            "thoughts_tokens": thoughts, "output_tokens": outtok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=6, help="타입별 세션 수")
    ap.add_argument("--log", default="out/session_log.jsonl")
    args = ap.parse_args()
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY 없음")
    client = genai.Client(api_key=key)

    # 세션 순서 섞기(human/agent 번갈아 아닌 랜덤).
    plan = []
    for _ in range(args.sessions):
        plan += ["human", "agent"]
    random.shuffle(plan)

    logp = Path(args.log); logp.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(1.0)
    sid = 0
    with open(logp, "w", encoding="utf-8") as f:
        for stype in plan:
            sid += 1
            cfg = TYPES[stype]
            n_turns = random.randint(*cfg["turns"])
            print(f"[세션 {sid}] {stype:6s} 턴={n_turns} gap={cfg['gap']} level={cfg['level']}")
            for ti in range(n_turns):
                q = random.choice(QUESTIONS)
                try:
                    m = ask(client, q, cfg["level"]); m["error"] = None
                except Exception as e:
                    m = {"error": f"{type(e).__name__}: {e}"}
                m.update({"session_id": sid, "session_type": stype,
                          "turn_idx": ti, "level": cfg["level"], "q": q[:30]})
                f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
                tag = m.get("error") or f"ttft={m.get('app_ttft_ms')}ms tok={m.get('thoughts_tokens')}"
                print(f"    t{ti} {tag}")
                # 턴 사이 gap(타입별).
                if ti < n_turns - 1:
                    time.sleep(random.uniform(*cfg["gap"]))
            time.sleep(SESSION_GAP)   # 세션 분리용 긴 공백
    print(f"\n[done] {sid}개 세션 -> {logp}")


if __name__ == "__main__":
    main()
