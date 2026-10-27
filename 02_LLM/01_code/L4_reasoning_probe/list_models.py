"""list_models.py — 내 Gemini 키로 쓸 수 있는 모델 목록. 비추론 baseline 고르기용.
사용: python3 list_models.py
작성일: 2026-09-01
"""
import os
from google import genai
c = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
for m in c.models.list():
    name = getattr(m, "name", "")
    methods = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None)
    if "generateContent" in (methods or []) or methods is None:
        print(name)
