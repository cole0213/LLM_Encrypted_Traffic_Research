"""
probe_usage.py — Claude / OpenAI 가 '실제 추론 토큰 수'를 usage 에 돌려주는지 확인한다.

왜 필요한가: 이 연구의 Task B(추론량 회귀)는 타깃이 realized 추론 토큰 수다.
      Gemini 는 usage_metadata.thoughts_token_count, Groq 은
      completion_tokens_details.reasoning_tokens 로 그 값을 준다.
      Claude / OpenAI 가 같은 값을 주는지는 캡처를 설계하기 전에 반드시 확인해야 한다.
      - 준다  -> Task A + Task B 둘 다 가능
      - 안 준다 -> Task A 만 가능(설정 라벨은 우리가 고르므로 항상 있다)

입력: ANTHROPIC_API_KEY 또는 OPENAI_API_KEY (있는 것만 검사)
출력: usage 객체 전체를 표준출력에 덤프. 추론 토큰으로 보이는 필드를 따로 표시.
사용: python3 probe_usage.py [--anthropic-model claude-haiku-5-5] [--openai-model ...]
비고: 1콜씩만 쓴다. 비용은 1원 미만.
작성일: 2026-11-06
"""
import os
import json
import argparse

# 추론 토큰이 담길 법한 필드 이름들. provider 마다 위치가 달라 전부 훑는다.
CANDIDATE_KEYS = (
    "thinking_tokens", "reasoning_tokens", "thoughts_token_count",
    "completion_reasoning_tokens", "reasoning_output_tokens",
)

# 암산을 강제해 추론이 실제로 일어나게 만드는 질문. 답은 391.
PROMPT = "17 x 23 을 암산으로 풀어라. 마지막 줄에 숫자만 출력."


def _to_dict(obj):
    """SDK 응답 객체를 dict 로 평탄화(판마다 메서드 이름이 달라 방어적으로)."""
    for meth in ("to_dict", "model_dump", "dict"):
        fn = getattr(obj, meth, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    if isinstance(obj, dict):
        return obj
    return {k: v for k, v in vars(obj).items() if not k.startswith("_")}


def find_reasoning_fields(d, path=""):
    """중첩 dict 를 훑어 추론 토큰으로 보이는 (경로, 값) 을 전부 모은다."""
    hits = []
    if isinstance(d, dict):
        for k, v in d.items():
            p = f"{path}.{k}" if path else k
            if isinstance(v, (dict, list)):
                hits += find_reasoning_fields(v, p)
            elif k in CANDIDATE_KEYS or ("reason" in k.lower() or "think" in k.lower()):
                hits.append((p, v))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            hits += find_reasoning_fields(v, f"{path}[{i}]")
    return hits


def probe_anthropic(model):
    """Claude 1콜. thinking 은 adaptive, effort=high 로 추론을 확실히 일으킨다."""
    import anthropic
    client = anthropic.Anthropic()
    # 주의: 현행 모델은 budget_tokens 를 받지 않는다(400). 깊이 제어는 effort 뿐이다.
    # 주의: temperature 는 2026-10-21 API 버전부터 전 모델 400 이다. 보내지 않는다.
    with client.messages.stream(
        model=model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": PROMPT}],
    ) as stream:
        for _ in stream:
            pass
        msg = stream.get_final_message()
    return _to_dict(msg.usage)


def probe_openai(model):
    """OpenAI 1콜. reasoning_effort 를 받는 모델이어야 의미가 있다."""
    from openai import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT}],
        reasoning_effort="high",
    )
    return _to_dict(r.usage)


def report(name, usage):
    print(f"\n=== {name} usage ===")
    print(json.dumps(usage, ensure_ascii=False, indent=2, default=str))
    hits = find_reasoning_fields(usage)
    if hits:
        print(f"\n[{name}] 추론 토큰 후보 필드:")
        for p, v in hits:
            print(f"  {p} = {v}")
        print(f"→ Task B 가능. 캡처 스크립트에서 이 경로를 thoughts_tokens 로 쓴다.")
    else:
        print(f"\n[{name}] 추론 토큰 필드 없음 → Task B 불가, Task A 만 가능.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anthropic-model", default="claude-haiku-5-5")
    ap.add_argument("--openai-model", default=None,
                    help="예: gpt-5-mini. 미지정이면 OpenAI 검사 생략")
    args = ap.parse_args()

    did = False
    if os.getenv("ANTHROPIC_API_KEY"):
        did = True
        try:
            report("anthropic", probe_anthropic(args.anthropic_model))
        except Exception as e:
            print(f"[anthropic] 실패: {type(e).__name__}: {e}")
    else:
        print("[anthropic] ANTHROPIC_API_KEY 없음 — 건너뜀")

    if args.openai_model:
        if os.getenv("OPENAI_API_KEY"):
            did = True
            try:
                report("openai", probe_openai(args.openai_model))
            except Exception as e:
                print(f"[openai] 실패: {type(e).__name__}: {e}")
        else:
            print("[openai] OPENAI_API_KEY 없음 — 건너뜀")

    if not did:
        raise SystemExit("검사할 provider 가 없다. 키를 export 하고 다시 실행.")


if __name__ == "__main__":
    main()
