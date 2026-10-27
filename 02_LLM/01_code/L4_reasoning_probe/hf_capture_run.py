"""
hf_capture_run.py — 인프라 격리 실험: HuggingFace Inference Providers(무료)로 gpt-oss-20b 요청.

목적: 서비스 비교의 confound(모델+인프라 동시변화) 제거. Groq(LPU·빠름)와 '같은 모델'
      gpt-oss-20b를 '느린 GPU 제공자'(Fireworks/Together 등)로 돌려 pkt_gap이 살아나는지 본다.
      살아나면 = "인프라 속도가 경계"를 격리 증명. 안 살아나면 = 가설 재검토(정직한 결과).

준비: pip install openai ; export HF_TOKEN=hf_...
     (무료 토큰: https://huggingface.co/settings/tokens , 카드 불필요, 월 무료 크레딧)
사용: hf_capture.sh 가 tcpdump와 함께 호출. 출력: out/hf_log.jsonl
비고:
  - HF 라우터는 OpenAI SDK 호환. base_url=https://router.huggingface.co/v1.
  - 제공자는 모델 슬러그 접미사로 지정: "openai/gpt-oss-20b:fireworks-ai"(느린 GPU=격리용).
    ★ ':cerebras'(웨이퍼)·Groq 같은 초고속은 쓰지 말 것 — 격리 깨짐(둘 다 평평).
  - 추론강도=reasoning_effort(low/med/high). 추론은 delta.reasoning으로 분리되어
    스트림 content 앞 '침묵'이 남음(Groq의 hidden과 동일 취지).
작성일: 2026-09-05
"""
import os
import json
import time
import argparse
from pathlib import Path

from openai import OpenAI

MODEL_BASE = "openai/gpt-oss-20b"
# 느린 GPU 제공자 기본값(격리용). 2026-09-05 현재 gpt-oss-20b 서빙 제공자:
#   together / deepinfra / novita / nscale / ovhcloud / featherless-ai (전부 느린 GPU=격리 OK),
#   groq (빠른 LPU=격리 금지). fireworks-ai는 이 모델 서빙 중단(410).
DEFAULT_PROVIDER = "together"
CONDITIONS = [
    ("think_low",  "low"),
    ("think_med",  "medium"),
    ("think_high", "high"),
]
# Groq/Gemini와 동일 질문(짧은 답 유도 = 출력 길이 통제).
QUESTIONS = [
    "17 x 23은? 답만.", "프랑스의 수도는? 답만.", "물이 어는 온도는? 답만.",
    "다음 논리 퍼즐: A>B>C>D 이고 D>A면 모순인가? 결론만.",
    "체스에서 나이트가 a1에서 h8까지 최소 몇 번? 답만.",
    "1~100 중 3의 배수도 5의 배수도 아닌 수 개수? 답만.",
    "수열 2,6,12,20,30 다음 항? 답만.", "24를 소인수분해하면? 답만.",
]


def run_one(client, model, question, effort):
    """스트리밍 요청. 벽시계 t_start/t_first_answer/t_end + 토큰수 반환.

    reasoning_effort=low/med/high 로 추론 깊이 조절. gpt-oss는 추론을 delta.reasoning
    으로 분리 스트리밍 → 첫 delta.content(=답 시작) 앞에 '침묵'이 남음(pkt_gap 신호).
    """
    t0 = time.time(); t_first = None
    answer_chars = 0; comp_tok = None; reason_chars = 0
    stream = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": question}],
        stream=True, temperature=0.6,
        reasoning_effort=effort,
    )
    for chunk in stream:
        t = time.time()
        ch = (chunk.choices or [None])[0]
        delta = getattr(ch, "delta", None) if ch else None
        txt = getattr(delta, "content", None) if delta else None
        reasoning = getattr(delta, "reasoning", None) if delta else None
        if reasoning:
            reason_chars += len(reasoning)
        if txt and txt.strip():
            if t_first is None:
                t_first = t
            answer_chars += len(txt)
        u = getattr(chunk, "usage", None)
        if u is not None:
            comp_tok = getattr(u, "completion_tokens", None) or comp_tok
    t_end = time.time()
    return {"t_start": t0, "t_first_answer": t_first, "t_end": t_end,
            "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
            "app_total_ms": round((t_end - t0) * 1000, 1),
            "answer_chars": answer_chars, "reason_chars": reason_chars,
            "output_tokens": comp_tok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--log", default="out/hf_log.jsonl")
    ap.add_argument("--provider", default=DEFAULT_PROVIDER,
                    help="HF 제공자(느린 GPU): together/deepinfra/novita/nscale/ovhcloud/featherless-ai. groq 금지(빠름).")
    # 아무 OpenAI 호환 제공자나 되게 일반화(HF/Nebius/Novita 공용).
    ap.add_argument("--base-url", default="https://router.huggingface.co/v1",
                    help="OpenAI 호환 엔드포인트. Nebius=https://api.tokenfactory.nebius.com/v1/")
    ap.add_argument("--key-env", default="HF_TOKEN",
                    help="API 키가 든 환경변수 이름. Nebius=NEBIUS_API_KEY")
    ap.add_argument("--model", default=None,
                    help="모델 전체 슬러그 직접 지정(예: Nebius는 openai/gpt-oss-20b). 없으면 HF식 base:provider.")
    args = ap.parse_args()
    key = os.getenv(args.key_env)
    if not key:
        raise SystemExit(f"{args.key_env} 없음 — 해당 제공자에서 무료 키 발급 후 export")
    model = args.model or f"{MODEL_BASE}:{args.provider}"
    client = OpenAI(base_url=args.base_url, api_key=key)
    print(f"base_url = {args.base_url}\nmodel = {model}")

    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS
    logp = Path(args.log); logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(qs) * len(CONDITIONS) * args.repeats; i = 0
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for qi, q in enumerate(qs):
            for cond, effort in CONDITIONS:
                for rep in range(args.repeats):
                    i += 1
                    try:
                        m = run_one(client, model, q, effort); m["error"] = None
                    except Exception as e:
                        m = {"error": f"{type(e).__name__}: {e}"}
                    m.update({"idx": i, "q_idx": qi, "condition": cond,
                              "service": "hf", "model": model,
                              "provider": args.provider, "effort": effort, "rep": rep})
                    f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
                    tag = m.get("error") or (f"ttft={m.get('app_ttft_ms')}ms "
                                             f"out={m.get('output_tokens')} think_chars={m.get('reason_chars')}")
                    print(f"[{i}/{total}] q{qi} {cond:10s} {tag}")
                    time.sleep(args.sleep)
    print(f"\n[done] -> {logp}")
    print(f"다음: parse_pcap.py <pcap> {logp} --local-ip <서버IP> --out out/hf_feats.csv")


if __name__ == "__main__":
    main()
