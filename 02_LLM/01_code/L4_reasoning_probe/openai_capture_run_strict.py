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
  python3 openai_capture_run_strict.py --list                      # 모델 목록
  python3 openai_capture_run_strict.py --probe --model a,b,c       # 모델당 1콜로 사전확인
  python3 openai_capture_run_strict.py --model <id> --api chat --repeats 3
입력: OPENAI_API_KEY. 출력: out/openai_log_strict.jsonl
비고: 파싱은 parse_pcap.py --out out/openai_strict.csv, 분류는 e1_from_csv.py.

  ⚠️ 모델 id·지원 effort 단계·엔드포인트는 **실행 전에 --list / --probe 로 확인할 것.**
     라인업이 자주 바뀌어 코드에 박아둔 기본값이 틀릴 수 있다.

  엔드포인트가 두 종류다. --probe 가 어느 쪽인지 알려주고, 본캡처는 --api 로 못박는다:
    chat      : reasoning_effort 가 평평한 최상위 인자,
                usage.completion_tokens_details.reasoning_tokens
    responses : reasoning={"effort": ...} 로 중첩,
                usage.output_tokens_details.reasoning_tokens
  본캡처에서 --api auto 는 금지다 — 콜마다 엔드포인트가 달라지면 요청 모양이 섞여
  캡처가 통째로 못 쓰게 된다.
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
DEFAULT_MODEL = "gpt-6-luna"

# Groq 과 같은 3단계를 기본으로 둔다(교차 비교가 목적이므로 단계를 맞추는 쪽이 중요하다).
#
# gpt-6 계열은 none / low / medium / high / xhigh / max 의 6단계를 받는다(공식 문서 기준,
# 단 gpt-6.1-sol 은 none 미지원). 'none' 은 Gemini 의 no_think 에 대응하는 진짜 추론 끄기로,
# Groq gpt-oss 에는 없던 조건이다 — 지금까지 '설정없음 vs high' 를 Gemini 로만 쟀다.
# 전 단계를 쓰려면:  --efforts none,low,medium,high,xhigh,max
# 단 단계를 늘리면 조건 수가 늘어 콜 수도 비례해 늘어난다. 예산을 보고 정할 것.
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


def _get(obj, name):
    """객체 속성이든 dict 키든 같은 방식으로 꺼낸다(SDK 판마다 달라서)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _reasoning_tokens(usage):
    """usage 에서 추론 토큰수를 방어적으로 추출.

    경로가 API 마다 다르다 — 둘 다 본다:
      Chat Completions : usage.completion_tokens_details.reasoning_tokens
      Responses        : usage.output_tokens_details.reasoning_tokens
    ※ reasoning_tokens 는 output 토큰 '안에' 포함된다. 비용 계산에서 따로 더하면 중복이다.
    """
    if usage is None:
        return None
    for det_key in ("completion_tokens_details", "output_tokens_details"):
        v = _get(_get(usage, det_key), "reasoning_tokens")
        if v is not None:
            return v
    for attr in ("reasoning_tokens", "completion_reasoning_tokens"):
        v = _get(usage, attr)
        if v:
            return v
    return None


def _output_tokens(usage):
    """생성 토큰 총량. Chat Completions 는 completion_tokens, Responses 는 output_tokens."""
    if usage is None:
        return None
    for k in ("completion_tokens", "output_tokens"):
        v = _get(usage, k)
        if v is not None:
            return v
    return None


def _input_tokens(usage):
    """입력 토큰. Chat Completions 는 prompt_tokens, Responses 는 input_tokens.

    누적 비용 계산에 쓴다. 추론 토큰은 output 쪽에 이미 포함돼 있으므로 따로 더하지 않는다.
    """
    if usage is None:
        return None
    for k in ("prompt_tokens", "input_tokens"):
        v = _get(usage, k)
        if v is not None:
            return v
    return None


def _stream_chat(client, model, prompt, effort, max_tok, include_usage):
    """Chat Completions 스트림. reasoning_effort 는 평평한 최상위 인자."""
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        # 추론 모델은 temperature 를 받지 않는다. 보내지 않는다(Groq 판과 다른 점).
        reasoning_effort=effort,
        max_completion_tokens=max_tok,
        # ⚠️ include_usage 는 마지막 청크에 usage 숫자를 실어 보낸다. 추론 토큰이 클수록
        #    그 숫자의 자릿수가 늘어 응답 바이트가 커진다 — 즉 **라벨을 수집하는 행위 자체가
        #    신호를 만들어낼 수 있다.** Groq 에서 이 가설이 제기됐고 아직 대조 캡처를 못 했다
        #    (HANDOFF 5-5). 여기선 끌 수 있게 열어둔다: --no-usage 로 대조군을 찍고
        #    두 캡처의 AUC 를 비교하면 교란 크기를 바로 잰다.
        #    단 --no-usage 면 thoughts_tokens 가 안 와서 Task B 라벨이 없다. Task A 전용.
        **({"stream_options": {"include_usage": True}} if include_usage else {}),
    )


def _stream_responses(client, model, prompt, effort, max_tok):
    """Responses 스트림. effort 가 reasoning 객체 안으로 들어가고 한계 인자 이름도 다르다.

    gpt-6 계열 문서가 usage 를 output_tokens_details 로 적고 있어 이쪽이 정본일 가능성이
    높다. 어느 쪽이 되는지는 --probe 가 가린다.
    """
    return client.responses.create(
        model=model,
        input=[{"role": "user", "content": prompt}],
        reasoning={"effort": effort},
        max_output_tokens=max_tok,
        stream=True,
    )


def _probe_call(client, model, prompt, effort, max_tok, which):
    """프로브 1콜. 성공하면 usage, 실패하면 예외를 그대로 올린다."""
    if which == "chat":
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort=effort,
            max_completion_tokens=max_tok)
    else:
        r = client.responses.create(
            model=model,
            input=[{"role": "user", "content": prompt}],
            reasoning={"effort": effort},
            max_output_tokens=max_tok)
    return r.usage


# 동적 범위가 이보다 좁으면 응답 바이트 차이가 수십 바이트에 그친다.
# 지금 탐지기는 수백~수천 바이트 차이를 보므로 사실상 신호가 없다.
MIN_USEFUL_RANGE = 50


def _verdict(got, label):
    """추론 토큰 목록 → 이 엔드포인트가 쓸 만한지 한 줄 판정."""
    got = [g for g in got if g is not None]
    if not got:
        return f"{label}: 추론 토큰 미보고 또는 전부 실패"
    lo, hi = min(got), max(got)
    if hi == 0:
        return f"{label}: 전 단계 추론 0 — 설정이 안 먹거나 문항이 쉽다"
    if hi - lo < MIN_USEFUL_RANGE:
        return f"{label}: 범위 {lo}~{hi} 로 너무 좁다 — 캡처해도 신호 없음"
    return f"{label}: 범위 {lo}~{hi} — 쓸 만하다"


# 문항이 쓸 만하다고 보는 최소 '설정 간 추론 토큰 격차'.
# 왜 이 값인가 — 추론 N 토큰은 대략 4N 바이트의 응답 증가로 나타난다(Gemini 실측에서 유추).
# 기준 응답이 1,400 바이트 안팎이므로, 격차 100 토큰 ≈ 400 바이트 ≈ 30% 변화라야
# TLS 레코드 패딩과 망 잡음을 넘어 분류기가 집어낼 수 있다. 20 토큰(≈80B, 6%)으로는 부족하다.
MIN_SPREAD = 100


def screen_questions(client, model, efforts, args):
    """전 문항을 **설정 전 단계로** 돌려 '설정 간 격차가 큰 문항'을 선별한다.

    기준이 "추론 > 0" 이 아니라 **"설정을 바꿨을 때 추론량이 얼마나 벌어지는가"** 인 게
    핵심이다. 모든 설정에서 20 토큰씩 쓰는 문항은 추론이 '일어나긴' 해도 설정을 구분할
    수 없어 라벨과 신호가 대응하지 않는다. 탐지 대상은 추론의 유무가 아니라 그 양이다.

    문항 세트는 2026-09~10 에 Gemini/Groq 기준으로 만들었다. 그 뒤 모델이 좋아져
    대부분이 1단계 계산·암기로 풀려버린다. 실측에서 살아남는 건 탐색·다단계 논리뿐이다
    (q4 체스 나이트 none=0 -> max=346, 나머지 대부분은 전 단계 20~40).

    여기서 걸러낸 문항 번호를 본캡처의 문항 세트로 쓴다.
    """
    which = "responses" if args.api == "auto" else args.api
    print(f"\n=== 문항 선별: {model} / {which} / efforts={','.join(efforts)} ===")
    hdr = f"{'q':>3}" + "".join(f"{e:>8}" for e in efforts) + f"{'격차':>8}  문항"
    print(hdr)
    rows = []
    for qi, q in enumerate(QUESTIONS):
        vals = []
        for effort in efforts:
            try:
                u = _probe_call(client, model, q + INSTR, effort, args.max_tok, which)
                vals.append(_reasoning_tokens(u) or 0)
            except Exception:
                # 지원 안 하는 단계(예: astra 의 none)는 격차 계산에서 빼야 한다.
                vals.append(None)
            time.sleep(args.sleep)
        got = [v for v in vals if v is not None]
        spread = (max(got) - min(got)) if got else 0
        rows.append((qi, spread, got))
        cells = "".join(f"{('—' if v is None else v):>8}" for v in vals)
        print(f"{qi:>3}{cells}{spread:>8}  {q[:44]}")

    rows.sort(key=lambda r: -r[1])
    good = [qi for qi, sp, _ in rows if sp >= MIN_SPREAD]
    print(f"\n격차 {MIN_SPREAD} 토큰 이상: {len(good)}/{len(rows)} 문항")
    print(f"  쓸 문항(격차순): {good}")
    print("  격차 상위 10:   " + ", ".join(f"q{qi}({sp})" for qi, sp, _ in rows[:10]))
    if len(good) < 10:
        print(f"\n⚠️ 쓸 수 있는 문항이 {len(good)}개뿐이다. 질문별 교차검증에서 독립 표본은")
        print("   사실상 문항 수이므로 이대로는 일반화를 주장할 수 없다.")
        print("   살아남은 문항의 성격(탐색·열거·다단계 논리)을 본떠 문항을 새로 만들 것.")
    return good


def probe_one(client, model, efforts, args):
    """모델 1개를 effort × 엔드포인트로 훑어 네 가지를 가린다.

      (1) 어느 엔드포인트가 추론을 실제로 돌리는가
      (2) usage 에 추론 토큰을 돌려주는가 → Task B(회귀) 가능 여부
      (3) **effort 를 올리면 추론 토큰이 실제로 늘어나는가** → 설정 축의 성립 여부
      (4) 한 콜이 토큰을 얼마나 먹는가 → 콜 수를 곱하면 풀런 예산

    (1) 을 두 엔드포인트 다 찍어 비교하는 게 핵심이다. 공식 문서가
    "모델 페이지에 엔드포인트 이름이 보인다고 전부 지원하는 건 아니다" 라고
    경고하고, 실제로 Chat Completions 는 400 을 내지 않으면서 추론을 건너뛸 수 있다.
    에러가 안 나니 그대로 수백 콜을 찍고 '신호 없음' 이라는 가짜 결론을 낸다.

    (3) 이 전 단계 0 이면 둘 중 하나다:
      - 문항이 너무 쉬워 모델이 추론을 생략했다 (--probe-q 로 어려운 문항 재확인)
      - reasoning_effort 가 무시되고 있다 (→ 이 모델·엔드포인트는 제외)
    """
    prompt = QUESTIONS[int(args.probe_q)] + INSTR
    apis = ["chat", "responses"] if args.api == "auto" else [args.api]
    # rows[effort][api] = (추론토큰, 출력토큰, 전체토큰, 에러)
    rows = {}
    for effort in efforts:
        rows[effort] = {}
        for which in apis:
            try:
                u = _probe_call(client, model, prompt, effort, args.max_tok, which)
                rows[effort][which] = (_reasoning_tokens(u), _output_tokens(u),
                                       _get(u, "total_tokens"), None)
            except Exception as e:
                rows[effort][which] = (None, None, None, f"{type(e).__name__}: {e}")

    print(f"\n=== {model}   (q{args.probe_q})")
    head = f"{'effort':<8}" + "".join(f"{a + ' 추론':>14}{a + ' 전체':>14}" for a in apis)
    print(head)
    for effort in efforts:
        line = f"{effort:<8}"
        for which in apis:
            rt, _ot, tot, err = rows[effort][which]
            # 지원 안 하는 단계·엔드포인트는 여기서 걸린다(예: astra·6.1-sol 의 none).
            line += f"{('ERR' if err else str(rt)):>14}{('—' if err else str(tot)):>14}"
        print(line)
    # 에러는 한 번씩만 풀어서 보여준다(같은 메시지가 단계마다 반복되므로).
    seen = set()
    for effort in efforts:
        for which in apis:
            err = rows[effort][which][3]
            if err and err not in seen:
                seen.add(err)
                print(f"  [{which}] {err[:140]}")

    for which in apis:
        print("→ " + _verdict([rows[e][which][0] for e in efforts], which))
    if len(apis) > 1:
        best = max(apis, key=lambda a: max(
            [rows[e][a][0] or 0 for e in efforts] or [0]))
        print(f"→ 본캡처 후보: --model {model} --api {best}")
    return rows


def run_one(client, model, question, effort, pad, instr=None, max_tok=None,
            include_usage=True, api="chat"):
    """스트리밍 요청. 벽시계 t_start/t_first_answer/t_end(pcap 정렬용) + 토큰수 반환.

    반환 필드는 groq_capture_run_strict.run_one 과 같은 이름을 쓴다 —
    parse_pcap.py 가 그 이름으로 읽기 때문이다.
    """
    prompt = question + (instr or INSTR) + (" " * pad)
    max_tok = max_tok or MAX_COMPLETION_TOKENS
    t0 = time.time(); t_first = None
    answer_chars = 0; comp_tok = None; think_tok = None; in_tok = None; finish = None
    # 추론 요약이 스트림에 실려 내려오는지 양으로 기록한다. 0 이면 '바이트 신호 없음'의
    # 직접 근거가 되고, 0 이 아니면 Gemini thoughtSignature 와 같은 누출 경로가 된다.
    reasoning_chars = 0
    # 추론 중 빈 keep-alive 청크가 바이트를 밀어올렸을 가능성을 배제하기 위한 대조.
    chunk_count = 0

    if api == "responses":
        stream = _stream_responses(client, model, prompt, effort, max_tok)
    else:
        stream = _stream_chat(client, model, prompt, effort, max_tok, include_usage)

    for chunk in stream:
        t = time.time()
        chunk_count += 1
        usage = None
        if api == "responses":
            # 이벤트 종류가 판마다 늘어나므로 이름으로 분기하지 않고 모양으로 집는다.
            et = str(getattr(chunk, "type", "") or "")
            d = getattr(chunk, "delta", None)
            if isinstance(d, str) and d:
                if "reasoning" in et:
                    reasoning_chars += len(d)
                else:
                    if t_first is None and d.strip():
                        t_first = t
                    answer_chars += len(d)
            resp = getattr(chunk, "response", None)
            if resp is not None:
                usage = getattr(resp, "usage", None)
                finish = getattr(resp, "status", None) or finish
        else:
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
            usage = getattr(chunk, "usage", None)
        if usage is not None:
            comp_tok = _output_tokens(usage) or comp_tok
            think_tok = _reasoning_tokens(usage) or think_tok
            in_tok = _input_tokens(usage) or in_tok
    t_end = time.time()
    return {"t_start": t0, "t_first_answer": t_first, "t_end": t_end,
            "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
            "app_total_ms": round((t_end - t0) * 1000, 1),
            "answer_chars": answer_chars,
            "thoughts_tokens": think_tok, "output_tokens": comp_tok,
            "input_tokens": in_tok,
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
                    help="effort 단계별로 1콜씩 돌려 추론 토큰이 실제로 늘어나는지 본다. 캡처 전 필수")
    ap.add_argument("--probe-q", default="0",
                    help="프로브에 쓸 문항 번호. 기본 0(17x23, 쉬움). "
                         "'all' 이면 전 문항을 한 단계로 훑어 난도를 선별한다 "
                         "(4=체스 나이트 경로탐색, 9=삼단논법, 16=수열 2^n-1)")
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
    # --- 예산 가드레일 -------------------------------------------------------
    # 무료 크레딧이 한정돼 있고 만료일도 있다. 추론 토큰은 설정·문항에 따라 수십 배로
    # 튀므로 '얼마 나올지'를 미리 알 수 없다. 그래서 돌면서 실제 usage 로 누적 비용을
    # 계산해 보여주고, 상한을 넘으면 스스로 멈춘다. 중간에 멈춰도 로그는 남으므로
    # 거기까지의 콜은 버리지 않는다.
    ap.add_argument("--price-in", type=float, default=None,
                    help="입력 단가($/1M). 주면 누적 비용을 표시한다")
    ap.add_argument("--price-out", type=float, default=None,
                    help="출력 단가($/1M). 추론 토큰이 여기 포함된다")
    ap.add_argument("--max-spend", type=float, default=None,
                    help="누적 비용이 이 금액($)을 넘으면 중단한다. 단가 2개와 함께 쓸 것")
    ap.add_argument("--api", default="auto", choices=["auto", "chat", "responses"],
                    help="어느 엔드포인트로 칠지. auto=chat 먼저 시도하고 실패하면 responses")
    ap.add_argument("--max-tok", type=int, default=8192,
                    help="max_completion_tokens / max_output_tokens. 추론 토큰이 "
                         "여기 포함되므로 xhigh·max 에선 넉넉해야 한다. 모자라면 추론 도중 "
                         "한계에 닿아 답이 안 나온다(truncated)")
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
        # 캡처를 설계하기 전에 세 가지를 한 번에 가린다.
        #   (1) 이 모델이 어느 엔드포인트를 받는가 (chat / responses)
        #   (2) 추론 토큰 수를 usage 에 돌려주는가 -> Task B 가능 여부
        #   (3) 한 콜이 토큰을 얼마나 먹는가 -> 풀런 예산 추정
        # --model 에 쉼표를 주면 여러 모델을 한 번에 훑는다(모델 × effort 단계 콜).
        efforts = [e for _, e, _ in conds]
        models = [m.strip() for m in args.model.split(",") if m.strip()]
        if str(args.probe_q).lower() == "all":
            # 문항 선별 모드. --efforts 전 단계를 돌려 문항별 '설정 간 격차'를 잰다.
            for mdl in models:
                screen_questions(client, mdl, efforts, args)
            return
        for mdl in models:
            probe_one(client, mdl, efforts, args)
        return

    # 본캡처에서 auto 는 쓰지 않는다 — 콜마다 엔드포인트가 달라지면 트래픽 모양이
    # 섞여 캡처가 못 쓰게 된다. --probe 가 알려준 값을 명시하도록 강제한다.
    if args.api == "auto":
        raise SystemExit("--api chat 또는 --api responses 를 명시할 것. "
                         "먼저 --probe 로 어느 쪽이 되는지 확인하라.")
    api = args.api

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
    # 누적 토큰·비용. 추론량은 설정·문항에 따라 수십 배로 튀어 사전 예측이 안 된다.
    # 실제 usage 로 누적해 보여주고, 상한을 넘으면 멈춘다(그때까지 로그는 남는다).
    sum_in = sum_out = 0
    show_cost = args.price_in is not None and args.price_out is not None
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for i, (qi, cond, effort, pad, rep, arm) in enumerate(trials, 1):
            instr, expect, max_tok = build_arm(arm)
            try:
                m = run_one(client, args.model, qs[qi], effort, pad,
                            instr=instr, max_tok=max(max_tok, args.max_tok),
                            include_usage=not args.no_usage,
                            api=api); m["error"] = None
            except Exception as e:
                m = {"error": f"{type(e).__name__}: {e}"}
            m.update({"idx": i, "order_idx": i, "q_idx": qi, "condition": cond,
                      "arm": arm, "expect_chars": expect,
                      # 자유 arm 은 기대 길이가 없어 준수 판정 대상이 아니다(None).
                      "complied": None if expect is None else m.get("answer_chars") == expect,
                      "service": "openai", "model": args.model, "effort": effort, "rep": rep,
                      "shuffled": not args.no_shuffle,
                      "include_usage": not args.no_usage, "api": api})
            f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
            tag = m.get("error") or (
                f"ttft={m.get('app_ttft_ms')}ms out={m.get('output_tokens')} "
                f"think={m.get('thoughts_tokens')} "
                f"chars={m.get('answer_chars')}" + ("" if expect is None else f"/{expect}")
                + ("" if m.get("complied") is not False else " [불일치]")
                + (" [잘림]" if m.get("truncated") else ""))
            sum_in += m.get("input_tokens") or 0
            sum_out += m.get("output_tokens") or 0
            cost = ((sum_in * args.price_in + sum_out * args.price_out) / 1e6
                    if show_cost else None)
            print(f"[{i}/{total}] q{qi} {cond:14s} arm={str(arm):<10s} {tag}"
                  + (f"  ${cost:.3f}" if show_cost else ""))
            if args.max_spend is not None and cost is not None and cost > args.max_spend:
                print(f"\n[중단] 누적 ${cost:.3f} > 상한 ${args.max_spend:.2f}. "
                      f"{i}/{total} 콜까지 로그에 남았다.")
                break
            time.sleep(args.sleep)
    print(f"\n[done] 로그 -> {logp}")
    print(f"토큰: 입력 {sum_in:,} / 출력 {sum_out:,}"
          + (f" / 비용 ${(sum_in * args.price_in + sum_out * args.price_out) / 1e6:.3f}"
             if show_cost else ""))
    print("→ 확인 1: answer_chars 가 조건 무관 고정인지(길이 통제 성공 여부)")
    print("→ 확인 2: truncated=true 건수(추론 폭주로 답이 없던 콜 — 분석서 제외)")
    print("→ 확인 3: thoughts_tokens 가 단계별로 벌어지는지(설정 반영 여부)")
    print("→ 확인 4: 파싱 후 조건별 up_bytes 중앙값이 같은지(요청 크기 통제 성공 여부)")


if __name__ == "__main__":
    main()
