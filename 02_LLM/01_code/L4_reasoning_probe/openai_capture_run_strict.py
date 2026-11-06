"""
openai_capture_run_strict.py — 길이 완전통제판 캡처 요청 생성기(OpenAI).

목적: groq_capture_run_strict.py(Groq/gpt-oss) 의 OpenAI 짝.
      같은 30문항·같은 단답강제·같은 arm 규격을 써서 provider 를 하나 더 늘린다.
      지금까지 데이터셋이 Gemini / Groq 20b / Groq 120b 셋뿐이라
      "일반화"라는 말을 쓸 수 없었다(HANDOFF 5-5). OpenAI 가 네 번째다.

      추론깊이 = reasoning_effort (Groq gpt-oss 와 같은 파라미터 이름·같은 의미).
      추론 요약을 스트림에 싣지 않으므로 Groq 의 reasoning_format="hidden" 과
      같은 상황이 된다 — 답 첫 토큰 앞에 '침묵'이 남는다.

프로토콜 공유: 문항·지시문·arm 정의는 groq_capture_run_strict 에서 **import 한다.**
      복붙하면 한쪽만 고쳐져 두 provider 의 조건이 조용히 어긋난다. 실제로 그런 사고가
      있었다(HANDOFF 3-7). 단일 출처를 강제하려고 일부러 import 로 묶었다.

준비: pip install openai ; export OPENAI_API_KEY=sk-...
사용: openai_capture_strict.sh 가 tcpdump 와 함께 호출(직접도 가능).
  python3 openai_capture_run_strict.py --list                 # 모델 목록부터 확인
  python3 openai_capture_run_strict.py --model <id> --repeats 3
입력: OPENAI_API_KEY. 출력: out/openai_log_strict.jsonl
비고: 파싱은 parse_pcap.py --out out/openai_strict.csv, 분류는 e1_from_csv.py.
  ⚠️ 모델 id 와 지원 effort 단계는 **실행 전에 --list / --probe 로 확인할 것.**
     모델 라인업이 자주 바뀌어 코드에 박아둔 기본값이 틀릴 수 있다.
작성일: 2026-11-06
"""
import os
import json
import time
import random
import argparse
from pathlib import Path

from openai import OpenAI

# 프로토콜 정의는 Groq 판이 정본이다. 두 provider 가 같은 문항·같은 지시문을 쓰도록 공유한다.
from groq_capture_run_strict import (
    QUESTIONS, INSTR, FREE_ARMS, build_arm, parse_arms, MAX_COMPLETION_TOKENS,
)

# ⚠️ 기본값일 뿐이다. --list 로 실제 사용 가능한 추론 모델을 확인하고 --model 로 지정하라.
DEFAULT_MODEL = "gpt-5-mini"

# Groq 과 같은 3단계를 기본으로 둔다(교차 비교가 목적이므로 단계를 맞추는 쪽이 중요하다).
# 모델이 더 많은 단계를 지원하면 --efforts 로 늘린다.
DEFAULT_EFFORTS = "low,medium,high"


def build_conditions(spec):
    """'low,medium,high' → [(조건명, effort), ...] + 요청크기 보정 패딩.

    요청 크기 누출 방지(HANDOFF 3-19 ①): reasoning_effort 값의 글자수가 단계마다 달라
    (low=3, medium=6, high=4 ...) 요청 바이트에 설정값이 그대로 남는다. 분류기가
    "추론했나"가 아니라 "설정 문자열이 길었나"를 읽어버린다.
    → 가장 긴 effort 문자열에 맞춰 프롬프트 끝에 공백을 덧붙여 상쇄한다.
    Groq 판은 3단계라 PAD_CHARS 를 손으로 박아뒀지만, 여기선 단계가 가변이라 계산한다.
    ※ 캡처 후 CSV 에서 조건별 up_bytes 중앙값이 같은지 반드시 재확인할 것.
    """
    efforts = [e.strip() for e in spec.split(",") if e.strip()]
    width = max(len(e) for e in efforts)
    conds = [(f"think_{e}", e, width - len(e)) for e in efforts]
    return conds


def _reasoning_tokens(usage):
    """usage 에서 추론 토큰수를 방어적으로 추출.

    OpenAI 는 completion_tokens_details.reasoning_tokens 에 넣는다. SDK 판에 따라
    객체이기도 dict 이기도 해서 둘 다 받는다. Groq 판의 같은 이름 함수와 동일한 이유다.
    """
    if usage is None:
        return None
    det = getattr(usage, "completion_tokens_details", None)
    if det is None and isinstance(usage, dict):
        det = usage.get("completion_tokens_details")
    if det is not None:
        v = getattr(det, "reasoning_tokens", None)
        if v is None and isinstance(det, dict):
            v = det.get("reasoning_tokens")
        if v is not None:
            return v
    for attr in ("reasoning_tokens", "completion_reasoning_tokens"):
        v = getattr(usage, attr, None)
        if v:
            return v
    return None


def run_one(client, model, question, effort, pad, instr=None, max_tok=None,
            include_usage=True):
    """스트리밍 요청. 벽시계 t_start/t_first_answer/t_end(pcap 정렬용) + 토큰수 반환.

    반환 필드는 groq_capture_run_strict.run_one 과 같은 이름을 쓴다 —
    parse_pcap.py 가 그 이름으로 읽기 때문이다.
    """
    t0 = time.time(); t_first = None
    answer_chars = 0; comp_tok = None; think_tok = None; finish = None
    # 추론 요약이 스트림에 실려 내려오는지 양으로 기록한다. 0 이면 '바이트 신호 없음'의
    # 직접 근거가 되고, 0 이 아니면 Gemini thoughtSignature 와 같은 누출 경로가 된다.
    reasoning_chars = 0
    # 추론 중 빈 keep-alive 청크가 바이트를 밀어올렸을 가능성을 배제하기 위한 대조.
    chunk_count = 0
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": question + (instr or INSTR) + (" " * pad)}],
        stream=True,
        # 추론 모델은 temperature 를 받지 않는다. 보내지 않는다(Groq 판과 다른 점).
        reasoning_effort=effort,
        max_completion_tokens=max_tok or MAX_COMPLETION_TOKENS,
        # ⚠️ include_usage 는 마지막 청크에 usage 숫자를 실어 보낸다. 추론 토큰이 클수록
        #    그 숫자의 자릿수가 늘어 응답 바이트가 커진다 — 즉 **라벨을 수집하는 행위 자체가
        #    신호를 만들어낼 수 있다.** Groq 에서 이 가설이 제기됐고 아직 대조 캡처를 못 했다
        #    (HANDOFF 5-5). 여기선 끌 수 있게 열어둔다: --no-usage 로 대조군을 찍고
        #    두 캡처의 AUC 를 비교하면 교란 크기를 바로 잰다.
        #    단 --no-usage 면 thoughts_tokens 가 안 와서 Task B 라벨이 없다. Task A 전용.
        **({"stream_options": {"include_usage": True}} if include_usage else {}),
    )
    for chunk in stream:
        t = time.time()
        chunk_count += 1
        ch = (chunk.choices or [None])[0] if getattr(chunk, "choices", None) else None
        if ch is not None and getattr(ch, "finish_reason", None):
            finish = ch.finish_reason
        delta = getattr(ch, "delta", None) if ch else None
        txt = getattr(delta, "content", None) if delta else None
        # 일부 모델/라우터는 추론 요약을 delta.reasoning 으로 따로 흘린다.
        reasoning = getattr(delta, "reasoning", None) if delta else None
        if reasoning:
            reasoning_chars += len(reasoning)
        if txt:
            if t_first is None and txt.strip():
                t_first = t
            answer_chars += len(txt)
        u = getattr(chunk, "usage", None)
        if u is not None:
            comp_tok = getattr(u, "completion_tokens", None) or comp_tok
            think_tok = _reasoning_tokens(u) or think_tok
    t_end = time.time()
    return {"t_start": t0, "t_first_answer": t_first, "t_end": t_end,
            "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
            "app_total_ms": round((t_end - t0) * 1000, 1),
            "answer_chars": answer_chars,
            "thoughts_tokens": think_tok, "output_tokens": comp_tok,
            "had_reasoning": bool(think_tok), "reasoning_chars": reasoning_chars,
            "chunk_count": chunk_count,
            "finish_reason": finish, "pad_chars": pad,
            # 답이 한 글자도 안 나왔으면 추론이 한계까지 간 것(Groq 1차 q4 에서 4건 발생).
            "truncated": answer_chars == 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--log", default="out/openai_log_strict.jsonl")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--efforts", default=DEFAULT_EFFORTS,
                    help="추론강도 단계(쉼표). 기본 low,medium,high = Groq 과 동일")
    ap.add_argument("--list", action="store_true", help="사용가능 모델 출력 후 종료")
    ap.add_argument("--probe", action="store_true",
                    help="1콜만 돌려 usage 를 통째로 덤프(추론 토큰 보고 여부 확인). 캡처 전 필수")
    ap.add_argument("--seed", type=int, default=20261106,
                    help="시행 순서 섞기용 시드(재현 가능하게 고정)")
    ap.add_argument("--arms", default="0",
                    help="응답 길이 arm. 정수=덧붙일 글자 수(길이 고정), free_brief/free_full=자유 응답")
    ap.add_argument("--no-shuffle", action="store_true",
                    help="섞지 않고 순서대로(비교용)")
    ap.add_argument("--no-usage", action="store_true",
                    help="stream_options.include_usage 를 끈다. usage 숫자 자릿수가 "
                         "응답 바이트를 부풀리는 교란의 대조군(HANDOFF 5-5). "
                         "단 추론 토큰 라벨이 안 와서 Task A 전용이 된다")
    args = ap.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 없음")
    client = OpenAI()

    if args.list:
        for m in sorted(x.id for x in client.models.list().data):
            print(m)
        return

    conds = build_conditions(args.efforts)

    if args.probe:
        # 캡처를 설계하기 전에 반드시 확인할 것: 이 모델이 추론 토큰 수를 돌려주는가.
        #   돌려준다 -> Task A + Task B(회귀) 둘 다 가능
        #   안 준다   -> Task A 만 가능
        r = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": QUESTIONS[0] + INSTR}],
            reasoning_effort=conds[-1][1],
            max_completion_tokens=MAX_COMPLETION_TOKENS,
        )
        u = r.usage
        dump = u.to_dict() if hasattr(u, "to_dict") else (
            u.model_dump() if hasattr(u, "model_dump") else vars(u))
        print(json.dumps(dump, ensure_ascii=False, indent=2, default=str))
        rt = _reasoning_tokens(u)
        print(f"\n추론 토큰 = {rt}")
        if rt is None:
            print("→ 추론 토큰을 안 돌려준다. Task A 만 가능(설정 라벨은 우리가 고르므로 있다).")
        elif rt == 0:
            print("→ 0 이다. 이 문항/설정에선 추론이 안 일어났다. effort·문항을 바꿔 재확인.")
        else:
            print("→ Task B 가능. 이 값을 회귀 타깃으로 쓴다.")
        return

    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS
    arms = parse_arms(args.arms)
    trials = [(qi, cond, effort, pad, rep, arm)
              for qi, _ in enumerate(qs)
              for cond, effort, pad in conds
              for rep in range(args.repeats)
              for arm in arms]
    if not args.no_shuffle:
        random.Random(args.seed).shuffle(trials)

    logp = Path(args.log); logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(trials)
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for i, (qi, cond, effort, pad, rep, arm) in enumerate(trials, 1):
            instr, expect, max_tok = build_arm(arm)
            try:
                m = run_one(client, args.model, qs[qi], effort, pad,
                            instr=instr, max_tok=max_tok,
                            include_usage=not args.no_usage); m["error"] = None
            except Exception as e:
                m = {"error": f"{type(e).__name__}: {e}"}
            m.update({"idx": i, "order_idx": i, "q_idx": qi, "condition": cond,
                      "arm": arm, "expect_chars": expect,
                      # 자유 arm 은 기대 길이가 없어 준수 판정 대상이 아니다(None).
                      "complied": None if expect is None else m.get("answer_chars") == expect,
                      "service": "openai", "model": args.model, "effort": effort, "rep": rep,
                      "shuffled": not args.no_shuffle,
                      "include_usage": not args.no_usage})
            f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
            tag = m.get("error") or (
                f"ttft={m.get('app_ttft_ms')}ms out={m.get('output_tokens')} "
                f"think={m.get('thoughts_tokens')} "
                f"chars={m.get('answer_chars')}" + ("" if expect is None else f"/{expect}")
                + ("" if m.get("complied") is not False else " [불일치]")
                + (" [잘림]" if m.get("truncated") else ""))
            print(f"[{i}/{total}] q{qi} {cond:14s} arm={str(arm):<10s} {tag}")
            time.sleep(args.sleep)
    print(f"\n[done] 로그 -> {logp}")
    print("→ 확인 1: answer_chars 가 조건 무관 고정인지(길이 통제 성공 여부)")
    print("→ 확인 2: truncated=true 건수(추론 폭주로 답이 없던 콜 — 분석서 제외)")
    print("→ 확인 3: thoughts_tokens 가 단계별로 벌어지는지(설정 반영 여부)")
    print("→ 확인 4: 파싱 후 조건별 up_bytes 중앙값이 같은지(요청 크기 통제 성공 여부)")


if __name__ == "__main__":
    main()
