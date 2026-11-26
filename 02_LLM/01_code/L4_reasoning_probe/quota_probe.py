"""quota_probe.py — Gemini 한 콜만 날려 실제 에러 메시지를 그대로 본다.

왜 필요한가:
  선별기는 에러를 잡아 요약만 보여주고, 그나마 run 이 끝나야 찍힌다. 그래서
  '왜' 실패하는지(분당 한도인지 일당 한도인지 토큰 한도인지)를 알 수 없다.
  한도의 종류에 따라 대응이 완전히 다르다 —
    분당(RPM)  : 간격을 벌리면 된다
    일당(RPD)  : 오늘은 끝. 리셋을 기다리거나 유료로 가야 한다
    토큰(TPM)  : 출력 상한을 줄이면 된다
  그래서 추측하지 말고 원문을 읽는다.

입력: GEMINI_API_KEY
출력: 성공이면 추론 토큰 수, 실패면 에러 전문
작성일: 2026-11-10
"""
import os
import sys

from google import genai
from google.genai import types

MODEL = os.getenv("PROBE_MODEL", "gemini-3.5-flash-lite")

key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not key:
    raise SystemExit("GEMINI_API_KEY 없음 — . ~/.llm_keys 했는지 확인하라")

client = genai.Client(api_key=key)
prompt = "2 + 2 = ? A) 3 B) 4 C) 5 D) 6\n\n정답 한 글자만 출력하라."

try:
    r = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=256,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    u = r.usage_metadata
    print(f"성공 — 모델 {MODEL}")
    print(f"  입력 {u.prompt_token_count} / 출력 {u.candidates_token_count} / "
          f"추론 {getattr(u, 'thoughts_token_count', None)}")
    print("→ 할당량 살아 있다. 선별 다시 돌려도 된다.")
except Exception as e:
    print(f"실패 — {type(e).__name__}")
    print("--- 에러 전문 ---")
    print(str(e))
    print("--- 끝 ---")
    print()
    t = str(e).lower()
    if "per day" in t or "perday" in t or "requestsperday" in t:
        print("→ 일당(RPD) 한도다. 오늘은 끝. 리셋 대기 또는 유료 전환.")
    elif "per minute" in t or "perminute" in t:
        print("→ 분당(RPM) 한도다. 간격을 벌리면 계속 쓸 수 있다.")
    elif "token" in t and "limit" in t:
        print("→ 토큰(TPM) 한도일 수 있다. max_output_tokens 를 줄여봐라.")
    else:
        print("→ 한도 종류가 메시지에 안 적혀 있다. quotaId / quotaMetric 줄을 봐라.")
    sys.exit(1)
