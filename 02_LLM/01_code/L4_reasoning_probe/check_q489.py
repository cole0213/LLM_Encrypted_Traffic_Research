"""check_q489.py — 불응으로 걸린 문항이 '거부'인지 '설명 덧붙임'인지 본다.

왜 필요한가:
  선별기는 답 글자 수가 1을 넘으면 불응으로 센다. 글자 수만 세고 텍스트는 버린다.
  그래서 모델이 답하기를 거부한 것인지, 답은 했는데 설명을 붙인 것인지 구분이 안 된다.
  둘은 대응이 다르다 —
    거부      : 안전 정책. provider 마다 달라 교차 비교가 깨진다. 문항을 빼야 한다.
    설명 덧붙임: 지시 준수 문제. 지시문을 세게 하면 문항을 살릴 수 있다.
  답변 원문을 그대로 찍어 눈으로 가린다.

입력: GEMINI_API_KEY, 인자로 문항 번호(기본 489)
출력: 조건별 답변 원문
작성일: 2026-11-12
"""
import os
import sys

from google import genai
from google.genai import types

from questions_all import QUESTIONS_V2_ALL, FAMILIES_V2_ALL

MODEL = "gemini-3.5-flash-lite"
INSTR = "\n\n정답 한 글자(A, B, C, D 중 하나)만 출력하라. 설명·다른 말·문장부호 금지."

qi = int(sys.argv[1]) if len(sys.argv) > 1 else 489
key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not key:
    raise SystemExit("GEMINI_API_KEY 없음")

client = genai.Client(api_key=key)
q = QUESTIONS_V2_ALL[qi]
print(f"q{qi}  템플릿={FAMILIES_V2_ALL[qi]}")
print(f"문항: {q}")
print()

# 세 설정 모두 본다. 거부라면 설정과 무관하게 거부하고,
# 지시 준수 문제라면 추론이 깊은 쪽에서 더 길어지는 경향이 있다.
for label, cfg in [
    ("no_think", None),
    ("low", types.ThinkingConfig(thinking_level="low")),
    ("high", types.ThinkingConfig(thinking_level="high")),
]:
    kw = {"max_output_tokens": 2048}
    if cfg is not None:
        kw["thinking_config"] = cfg
    try:
        r = client.models.generate_content(
            model=MODEL, contents=q + INSTR,
            config=types.GenerateContentConfig(**kw))
        txt = (r.text or "")
        u = r.usage_metadata
        print(f"[{label}] 추론토큰={getattr(u, 'thoughts_token_count', None)} "
              f"답글자수={len(txt.strip())}")
        print(f"  답변 원문: {txt.strip()!r}")
    except Exception as e:
        print(f"[{label}] 실패 — {type(e).__name__}: {e}")
    print()
