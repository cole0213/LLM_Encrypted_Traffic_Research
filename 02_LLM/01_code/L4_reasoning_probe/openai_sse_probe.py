#!/usr/bin/env python3
"""OpenAI Responses 스트림이 추론 중 무엇을 내려보내는지 원시 이벤트로 확인한다.

왜 필요한가
-----------
2026-11-20 전수 분석에서 OpenAI 3모델이 `thoughtSignature` 에 해당하는 필드를
**하나도 안 보내는데도**(sig_chars 3,750콜 전부 0) 하향 바이트가 추론 토큰당
약 35바이트씩 늘어난다는 것이 확인됐다. Claude/Gemini 의 3.1~3.9 B/tok 의 약 10배다.

그런데 기전을 모른다. 지금까지 배제된 것:
  - 추론 요약 텍스트가 아니다 (캡처 스크립트가 요약을 요청하지 않고, 로그의
    thought_chars 가 전 provider 0).
  - SSE 청크 '개수'가 아니다 (chunk_count 중앙값이 11로 거의 고정).
배제되지 않은 것: 추론 중 주기적으로 내려오는 무언가. 추론토큰당 하향 **패킷** 수가
OpenAI 0.015~0.017 vs Claude/Gemini 0.001~0.002 로 8~16배다.

무엇을 하는가
-------------
같은 문항을 effort 를 바꿔 호출하면서 **모든 SSE 이벤트를 종류별로 집계**한다.
이벤트 타입, 개수, 직렬화 길이 합계를 effort 간에 대조하면 무엇이 늘어나는지 보인다.
`--dump` 를 주면 이벤트 원문(앞 N자)까지 찍는다 — 새 필드가 보이면 거기 답이 있다.

입력 : 환경변수 OPENAI_API_KEY
출력 : 표준출력 표. `--out` 을 주면 이벤트 집계를 JSON 으로도 남긴다.
비용 : 모델 x effort 수만큼 1콜. 단답 문항이라 전부 합쳐 $0.01 수준.

사용:
    python3 openai_sse_probe.py
    python3 openai_sse_probe.py --models gpt-6.1-sol --efforts low,max --dump 400
    python3 openai_sse_probe.py --out out/sse_probe.json

작성일: 2026-11-20
"""
from __future__ import annotations

import argparse
import json
import os
import time

from openai import OpenAI

# 본 캡처와 같은 단답 강제 지시문을 쓴다. 지시문이 다르면 응답 구조가 달라져
# "본 캡처에서 본 그 바이트"를 설명하지 못한다.
INSTR = "답을 한 글자로만 출력하라. 설명·단위·문장부호를 쓰지 마라."

# 추론량이 effort 에 따라 크게 벌어지는 문항이어야 대조가 선다.
# 너무 쉬우면 전 단계가 바닥에 붙어 차이가 안 보인다.
PROBE_Q = (
    "한 변의 길이가 8인 정사각형 격자에서 왼쪽 아래 칸에서 오른쪽 위 칸까지 "
    "오른쪽 또는 위로만 이동하는 경로 중, 대각선을 넘지 않는 경로의 개수를 구하라. "
    "그 수의 일의 자리 숫자만 출력하라. " + INSTR
)


def summarize_event(ev) -> tuple[str, int, str]:
    """이벤트 하나를 (타입, 직렬화 길이, 원문) 으로 만든다.

    길이는 SDK 객체를 JSON 으로 되돌린 길이다. 실제 와이어 바이트와 정확히 같지는
    않지만(SSE 프레이밍·TLS 오버헤드 제외) **어느 이벤트가 큰지**를 비교하는 데는
    충분하다. 절대 바이트는 pcap 쪽에서 이미 재고 있다.
    """
    et = str(getattr(ev, "type", "") or type(ev).__name__)
    try:
        raw = ev.model_dump_json()           # pydantic v2 (현행 SDK)
    except Exception:
        try:
            raw = json.dumps(ev, default=str)
        except Exception:
            raw = repr(ev)
    return et, len(raw), raw


def run_one(client: OpenAI, model: str, effort: str, max_tok: int, dump: int):
    """1콜. 이벤트를 전부 받아 타입별로 집계한다."""
    t0 = time.time()
    stream = client.responses.create(
        model=model,
        input=[{"role": "user", "content": PROBE_Q}],
        reasoning={"effort": effort},
        max_output_tokens=max_tok,
        stream=True,
    )
    by_type: dict[str, dict] = {}
    n = 0
    ttft_ms = None
    usage = None
    samples: list[str] = []
    for ev in stream:
        n += 1
        if ttft_ms is None:
            ttft_ms = (time.time() - t0) * 1000.0
        et, ln, raw = summarize_event(ev)
        slot = by_type.setdefault(et, {"n": 0, "bytes": 0, "max": 0})
        slot["n"] += 1
        slot["bytes"] += ln
        slot["max"] = max(slot["max"], ln)
        if dump and len(samples) < 40:
            samples.append(f"{et}  len={ln}  {raw[:dump]}")
        # usage 는 보통 마지막 response.completed 이벤트 안에 실려 온다
        resp = getattr(ev, "response", None)
        if resp is not None and getattr(resp, "usage", None) is not None:
            usage = resp.usage
    total_ms = (time.time() - t0) * 1000.0

    think = None
    out_tok = None
    if usage is not None:
        out_tok = getattr(usage, "output_tokens", None)
        det = getattr(usage, "output_tokens_details", None)
        if det is not None:
            think = getattr(det, "reasoning_tokens", None)
    return {
        "model": model, "effort": effort, "events": n,
        "ttft_ms": round(ttft_ms or 0, 1), "total_ms": round(total_ms, 1),
        "thoughts_tokens": think, "output_tokens": out_tok,
        "by_type": by_type, "samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="gpt-6-luna,gpt-6.1-terra,gpt-6.1-sol",
                    help="쉼표로 구분. 본 캡처에 쓴 3모델이 기본")
    ap.add_argument("--efforts", default="low,max",
                    help="대조할 effort. 양 끝만 봐도 무엇이 늘어나는지 보인다")
    ap.add_argument("--max-tok", type=int, default=8192,
                    help="본 캡처와 같은 값을 쓴다. 바꾸면 비교가 깨진다")
    ap.add_argument("--dump", type=int, default=0,
                    help="이벤트 원문 앞 N자를 찍는다. 새 필드를 눈으로 찾을 때")
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--out", default="", help="집계를 JSON 으로 저장할 경로")
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY 가 없다. `source ~/.llm_keys` 먼저.")
    client = OpenAI(api_key=key)

    models = [x.strip() for x in args.models.split(",") if x.strip()]
    efforts = [x.strip() for x in args.efforts.split(",") if x.strip()]
    results = []

    for model in models:
        print(f"\n{'='*72}\n[{model}]")
        rows = []
        for eff in efforts:
            try:
                r = run_one(client, model, eff, args.max_tok, args.dump)
            except Exception as e:
                print(f"  {eff:6s} 실패: {str(e)[:120]}")
                continue
            rows.append(r)
            results.append(r)
            print(f"  {eff:6s} 이벤트 {r['events']:4d}  추론 {r['thoughts_tokens']}"
                  f"  출력 {r['output_tokens']}  TTFT {r['ttft_ms']}ms  총 {r['total_ms']}ms")
            time.sleep(args.sleep)

        if len(rows) >= 2:
            # 두 effort 의 이벤트 타입별 차이. 추론량에 비례해 늘어나는 타입이 범인이다.
            lo, hi = rows[0], rows[-1]
            dt = (hi["thoughts_tokens"] or 0) - (lo["thoughts_tokens"] or 0)
            print(f"\n  추론토큰 차 {dt}  — 이벤트 타입별 증가분")
            print(f"  {'type':<44}{'개수 차':>9}{'바이트 차':>11}{'tok당B':>9}")
            keys = sorted(set(lo["by_type"]) | set(hi["by_type"]))
            tot_b = 0
            for k in keys:
                a = lo["by_type"].get(k, {"n": 0, "bytes": 0})
                b = hi["by_type"].get(k, {"n": 0, "bytes": 0})
                dn, db = b["n"] - a["n"], b["bytes"] - a["bytes"]
                tot_b += db
                if dn == 0 and db == 0:
                    continue
                per = (db / dt) if dt else 0.0
                print(f"  {k[:44]:<44}{dn:>9}{db:>11}{per:>9.2f}")
            print(f"  {'(합계)':<44}{'':>9}{tot_b:>11}{(tot_b/dt if dt else 0):>9.2f}")
            print("  → pcap 실측은 약 35 B/추론토큰이었다. 위 합계가 그에 근접하면"
                  " 범인은 이 이벤트들이고, 한참 모자라면 프레이밍·재전송 쪽이다.")

        if args.dump:
            for r in rows:
                print(f"\n  --- {r['effort']} 원문 표본 ---")
                for s in r["samples"]:
                    print("   ", s)

    if args.out:
        # samples 는 길어서 뺀다. 집계만 남긴다.
        slim = [{k: v for k, v in r.items() if k != "samples"} for r in results]
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, indent=1)
        print(f"\n[out] {args.out}")


if __name__ == "__main__":
    main()
