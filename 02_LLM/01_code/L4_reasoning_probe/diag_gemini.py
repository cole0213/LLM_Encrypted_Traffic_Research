"""
diag_gemini.py — gemini-3.6-flash가 어떤 thinking 설정을 받는지 알아내는 진단.
여러 config 변형을 한 질문에 시도해 PASS/FAIL + 에러를 출력한다. (비스트리밍, 소량)
사용: python3 diag_gemini.py
작성일: 2026-09-01
"""
import os
from google import genai
from google.genai import types

MODEL = "gemini-3.6-flash"
Q = "17 x 23은? 답만."

key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=key)

# ThinkingConfig가 어떤 필드를 갖는지 먼저 출력(SDK 버전 파악).
try:
    print("ThinkingConfig fields:", list(types.ThinkingConfig.model_fields.keys()))
except Exception as e:
    print("fields introspect fail:", e)

def try_variant(name, config):
    try:
        r = client.models.generate_content(model=MODEL, contents=Q, config=config)
        txt = (r.text or "")[:40].replace("\n", " ")
        um = getattr(r, "usage_metadata", None)
        tt = getattr(um, "thoughts_token_count", None) if um else None
        print(f"  PASS  {name:38s} -> '{txt}'  thoughts_tok={tt}")
    except Exception as e:
        print(f"  FAIL  {name:38s} -> {type(e).__name__}: {str(e)[:90]}")

print("\n=== 변형 시도 ===")
# A) 설정 없음(가장 기본)
try_variant("plain (no config)", None)
# B) thinking_budget 계열
try_variant("thinking_budget=512+include_thoughts",
            types.GenerateContentConfig(thinking_config=types.ThinkingConfig(
                thinking_budget=512, include_thoughts=True)))
try_variant("thinking_budget=512 (no include)",
            types.GenerateContentConfig(thinking_config=types.ThinkingConfig(
                thinking_budget=512)))
try_variant("thinking_budget=0",
            types.GenerateContentConfig(thinking_config=types.ThinkingConfig(
                thinking_budget=0)))
# C) thinking_level 계열(Gemini 3 신규일 수 있음)
for lvl in ["low", "high"]:
    try:
        cfg = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(
            thinking_level=lvl, include_thoughts=True))
        try_variant(f"thinking_level={lvl}+include", cfg)
    except Exception as e:
        print(f"  SKIP  thinking_level={lvl} (SDK에 필드 없음): {type(e).__name__}")
