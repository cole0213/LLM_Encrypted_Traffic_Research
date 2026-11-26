#!/usr/bin/env python3
"""Gemini 의 thinking_level 이 어느 단계까지 받는지, 어느 모델이 쓸 수 있는지 실측한다.

왜 필요한가
-----------
Anthropic·OpenAI 본 캡처는 low/medium/high/xhigh/max 5단으로 찍었는데, Gemini 를 같은
5단으로 다시 찍을 수 있는지가 불확실하다. 2026-11-19 공식 문서 확인 결과:
  - `max` 는 Gemini 에 아예 없다(Claude 전용 값).
  - `xhigh` 는 Gemini 4 Hydrogen / Neon 에만 있고, 지금 쓰는 gemini-3.5-flash-lite 에는 없다.
문서는 모델별 표가 자주 바뀌고 서드파티 사본끼리도 어긋나므로, 돈·시간을 쓰기 전에
**실제 API 응답으로** 확정한다. 400 이 나면 그 단계는 없는 것이다.

무엇을 하는가
-------------
1. models.list 로 이 API 키가 실제로 쓸 수 있는 모델을 찍는다(문서가 아니라 계정 기준).
2. 지정한 모델들에 thinking_level 후보값을 하나씩 넣어 1콜씩 보낸다.
   성공하면 실제로 추론 토큰이 몇 개 나왔는지까지 본다 — 값을 **받기만 하고 무시**하는
   경우가 있어서(예: 단계가 달라도 토큰이 같으면 쓸모없다) 수락 여부만으로는 부족하다.

입력 : 환경변수 GEMINI_API_KEY (또는 GOOGLE_API_KEY)
출력 : 표준출력 표. 파일은 안 만든다.
비용 : 모델 x 단계 수만큼의 1콜. 짧은 문항이라 무시할 수준.

사용:
    python3 gemini_level_probe.py
    python3 gemini_level_probe.py --models gemini-3.5-flash-lite,gemini-4-neon
    python3 gemini_level_probe.py --list-only

작성일: 2026-11-19
"""
from __future__ import annotations

import argparse
import os
import sys

# 본 캡처(capture_run_strict.py)와 같은 SDK 경로를 쓴다. 다른 경로로 재면
# "되는데 캡처에선 안 된다" 같은 어긋남이 생긴다.
from google import genai
from google.genai import types

# 단계 후보. Claude/OpenAI 5단 + Gemini 쪽에만 있다고 알려진 minimal 을 함께 본다.
# 순서는 약한 쪽부터 — 중간에 400 이 나도 어디까지 되는지 경계가 보인다.
LEVELS = ["minimal", "low", "medium", "high", "xhigh", "max"]

# 추론을 강제하되 답은 짧게 끝나는 문항. 단계가 실제로 토큰량을 바꾸는지 보려면
# 너무 쉬우면 안 되고(전 단계 0), 너무 어려우면 비용이 튄다.
PROBE_Q = (
    "A와 B 중 한 명만 진실을 말한다. "
    "A: 'B는 거짓말쟁이다.' B: '우리 둘 다 거짓말쟁이다.' "
    "거짓말쟁이는 누구인가? 답을 A 또는 B 한 글자로만 출력하라."
)


def get_client() -> genai.Client:
    """API 키를 환경변수에서만 읽는다. 키를 인자로 받지 않는 이유는
    셸 히스토리와 ps 출력에 남기지 않기 위해서다."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit(
            "GEMINI_API_KEY 가 없다. `source ~/.llm_keys` 를 먼저 하고 다시 실행하라."
        )
    return genai.Client(api_key=key)


def list_models(client: genai.Client) -> list[str]:
    """이 키로 generateContent 를 호출할 수 있는 모델만 추린다.
    문서의 모델 표가 아니라 계정 기준이라, 권한·지역 문제까지 같이 걸러진다."""
    out = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if actions and "generateContent" not in actions:
            continue
        out.append(getattr(m, "name", "") .replace("models/", ""))
    return sorted(out)


def probe(client: genai.Client, model: str, level: str) -> tuple[str, int | None]:
    """한 모델·한 단계에 1콜. (판정, 추론토큰) 을 돌려준다.

    판정은 셋 중 하나다.
      OK      — 수락됐고 응답이 왔다
      400     — 거부됐다. 그 단계는 이 모델에 없다
      ERR:... — 그 밖의 실패(권한·쿼터·네트워크). 단계 유무와 무관하므로 구분해 둔다
    """
    try:
        cfg = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=level),
            max_output_tokens=8192,
        )
        r = client.models.generate_content(model=model, contents=PROBE_Q, config=cfg)
    except Exception as e:  # SDK 가 예외 타입을 모델별로 달리 던져 폭넓게 받는다
        msg = str(e).replace("\n", " ")
        # 400 과 그 밖의 실패를 반드시 가른다. 쿼터 초과를 '미지원'으로 읽으면
        # 멀쩡한 단계를 영영 안 쓰게 된다.
        if "400" in msg or "INVALID_ARGUMENT" in msg:
            return "400", None
        return f"ERR:{msg[:70]}", None

    usage = getattr(r, "usage_metadata", None)
    tok = getattr(usage, "thoughts_token_count", None) if usage else None
    return "OK", tok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="gemini-3.5-flash-lite",
                    help="쉼표로 구분한 모델 목록. 기본은 본 캡처에 쓰는 모델 하나")
    ap.add_argument("--levels", default=",".join(LEVELS),
                    help="시험할 thinking_level 후보(쉼표)")
    ap.add_argument("--list-only", action="store_true",
                    help="모델 목록만 찍고 끝낸다. 콜을 한 개도 안 보낸다")
    args = ap.parse_args()

    client = get_client()

    print("=== 이 키로 쓸 수 있는 모델 ===")
    try:
        names = list_models(client)
        for n in names:
            # thinking 계열만 눈에 띄게 표시한다. 전부 찍으면 임베딩까지 섞여 읽기 어렵다
            mark = " <-- thinking 후보" if any(
                k in n for k in ("gemini-4", "gemini-3")) else ""
            print(f"  {n}{mark}")
    except Exception as e:
        print(f"  (목록 실패: {str(e)[:120]})")

    if args.list_only:
        return

    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    models = [x.strip() for x in args.models.split(",") if x.strip()]

    print(f"\n=== thinking_level 수락 여부 (문항 1개, 모델x단계 1콜씩) ===")
    for model in models:
        print(f"\n[{model}]")
        print(f"  {'단계':<9} {'판정':<10} 추론토큰")
        ok_levels = []
        for lv in levels:
            verdict, tok = probe(client, model, lv)
            if verdict == "OK":
                ok_levels.append(lv)
            print(f"  {lv:<9} {verdict:<10} {'' if tok is None else tok}")
        print(f"  => 수락된 단계: {','.join(ok_levels) if ok_levels else '없음'}")
        if len(ok_levels) >= 2:
            print("     ※ 수락됐다고 쓸모 있는 건 아니다. 위 추론토큰이 단계별로 "
                  "실제로 달라야 조건으로 쓸 수 있다.")


if __name__ == "__main__":
    main()
