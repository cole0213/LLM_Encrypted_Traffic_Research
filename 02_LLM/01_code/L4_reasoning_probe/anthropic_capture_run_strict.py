"""
anthropic_capture_run_strict.py — 길이 완전통제판(Anthropic Claude).

목적: Gemini·OpenAI 와 **같은 문항·같은 조건·같은 로그 형식**으로 Claude 트래픽을 받는다.
      A/B/C/D 단답을 강제해 응답 길이를 고정한 뒤, 추론 설정만 바꿔 가며 스트리밍 호출하고
      벽시계 시각을 남긴다. tcpdump 로 뜬 pcap 과 이 로그를 parse_pcap.py 가 맞물린다.

입력: --qset/--qfile 로 고른 문항, --efforts 로 고른 추론 단계, ANTHROPIC_API_KEY
출력: JSONL 로그 1줄 = 1콜. 필드 이름은 groq/openai/gemini 러너와 **반드시 동일**하다
      (parse_pcap.py 가 그 이름으로 읽는다).

Claude 가 앞선 두 provider 와 다른 점 — 러너를 따로 쓴 이유:
  1. 추론 단계가 `reasoning_effort` 가 아니라 **`output_config.effort`** 다.
     값은 low/medium/high/xhigh/max 5개. OpenAI 의 `none`·`minimal` 에 해당하는 값이 없다.
  2. **추론을 끌 수 없는 모델이 있다.** Opus 5.5 는 `thinking={"type":"disabled"}` 가
     모든 effort 에서 400 이다. 그래서 '추론 off' 조건은 이 러너에 두지 않는다.
  3. 추론 토큰을 usage 에 분리해 주는지가 **2026-11-17 현재 미확인**이다.
     Task B(realized 토큰 회귀) 라벨이 걸린 문제라, usage 를 통째로 `usage_raw` 에 적어
     나중에 어느 필드가 추론인지 확인할 수 있게 해 둔다. 확인되면 _reasoning_tokens 를 고친다.
  4. thinking 블록에 **`signature`** 가 실린다(멀티턴에서 추론 맥락을 유지하는 값).
     Gemini `thoughtSignature` 와 같은 자리이고, 거기서 "내용은 암호화돼도 길이가 샌다"가
     확인됐으므로 길이를 `sig_chars` 로 남긴다. **이 연구의 핵심 가설 검증점이다.**

사용: tcpdump 를 띄운 뒤 호출하는 게 정석이다 — anthropic_capture_strict.sh 를 쓸 것.
      python3 -u anthropic_capture_run_strict.py --log out/x.jsonl \
          --model claude-haiku-5-5 --qset v2 --qfile out/qfile_gemini481.json \
          --efforts low,medium,high,xhigh,max --repeats 1 --sleep 3

모델 선택 메모(2026-11-17 단가):
      claude-opus-5-5   $4 / $20  per 1M   — 기본값
      claude-sonnet-5-5 $2 / $10           — 중간
      claude-haiku-5-5  $0.10 / $0.50      — OpenAI gpt-6-luna 와 같은 단가대
      481문항 × 5단계 = 2,405콜 기준 거친 추정: haiku $0.6 / sonnet $12 / opus $24.
      셋 다 돌려도 랩비 $70 안에 들어간다.

작성일: 2026-11-17
"""
import os
import time
import json
import random
import argparse
from pathlib import Path

try:
    import anthropic
except ImportError:
    raise SystemExit("anthropic 패키지가 없다: pip install anthropic")

# 문항과 지시문은 다른 provider 와 **같은 것**을 써야 한다. 여기서 새로 정의하면
# 글자 하나만 달라도 provider 비교가 깨진다. 그래서 전부 import 한다.
from groq_capture_run_strict import (
    QUESTIONS as QUESTIONS_BASE, INSTR, select_questions,
)
from questions_hard import QUESTIONS_HARD
try:
    from questions_all import QUESTIONS_V2_ALL
except Exception:
    QUESTIONS_V2_ALL = None

QSETS = {"base": QUESTIONS_BASE, "hard": QUESTIONS_HARD}
if QUESTIONS_V2_ALL is not None:
    QSETS["v2"] = QUESTIONS_V2_ALL

# Opus 5.5 가 기본. 비용이 부담되면 --model claude-haiku-5-5 로 내린다(위 메모 참조).
DEFAULT_MODEL = "claude-opus-5-5"

# Claude 의 effort 단계. OpenAI 와 겹치는 다섯 개이고, Gemini 와 겹치는 건 low/medium/high 셋뿐이다.
DEFAULT_EFFORTS = "low,medium,high,xhigh,max"

# 추론 토큰이 max_tokens 를 같이 먹는다. Gemini(8192)·OpenAI(8192)와 맞춘다.
MAX_TOKENS = 8192


def build_conditions(spec):
    """'low,medium,high' → [(조건명, effort, 패딩공백수), ...]

    요청 바이트 누출 방지: effort 값의 글자수가 단계마다 달라(low=3 … medium=6)
    요청 크기에 설정값이 그대로 남는다. 그러면 분류기가 "추론했나"가 아니라
    "설정 문자열이 길었나"를 읽는다. 가장 긴 값에 맞춰 프롬프트 끝에 공백을 덧붙여 상쇄한다.
    OpenAI 러너의 build_conditions 와 같은 계산식이라 두 provider 의 패딩이 일치한다.
    ※ 캡처 후 CSV 에서 조건별 up_bytes 중앙값이 같은지 반드시 재확인할 것.
    """
    efforts = [e.strip() for e in spec.split(",") if e.strip()]
    if not efforts:
        raise SystemExit("--efforts 가 비었다")
    width = max(len(e) for e in efforts)
    return [(f"think_{e}", e, width - len(e)) for e in efforts]


def _get(obj, name):
    """속성이든 dict 키든 같은 방식으로 꺼낸다(SDK 판마다 달라서)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _usage_dict(usage):
    """usage 객체를 dict 로. 어떤 필드가 오는지 모르니 통째로 남겨 둔다."""
    if usage is None:
        return None
    for meth in ("to_dict", "model_dump"):
        fn = getattr(usage, meth, None)
        if callable(fn):
            try:
                return {k: v for k, v in fn().items() if v is not None}
            except Exception:
                pass
    if isinstance(usage, dict):
        return {k: v for k, v in usage.items() if v is not None}
    return None


# 추론 토큰이 어느 이름으로 오는지 2026-11-17 현재 확인되지 않았다.
# 그래서 후보를 순서대로 훑고, 하나도 없으면 None 을 남긴다(0 이 아니다 —
# '추론을 안 했다'와 '보고를 안 한다'를 섞으면 Task B 라벨이 조용히 망가진다).
_THINK_KEYS = ("thinking_tokens", "reasoning_tokens", "thought_tokens",
               "output_thinking_tokens", "reasoning_output_tokens")


def _reasoning_tokens(usage):
    """usage 에서 추론 토큰을 찾는다. 못 찾으면 None."""
    if usage is None:
        return None
    for k in _THINK_KEYS:
        v = _get(usage, k)
        if isinstance(v, int):
            return v
    # 중첩 형태(OpenAI 의 output_tokens_details 같은)도 한 겹 들여다본다.
    for outer in ("output_tokens_details", "completion_tokens_details", "details"):
        d = _get(usage, outer)
        if d is not None:
            for k in _THINK_KEYS:
                v = _get(d, k)
                if isinstance(v, int):
                    return v
    return None


def run_one(client, model, question, effort, pad, max_tok=MAX_TOKENS):
    """스트리밍 요청 1회. 벽시계 t_start/t_first_answer/t_end(pcap 정렬용)와 토큰수를 돌려준다.

    반환 필드 이름은 다른 러너와 **같아야 한다** — parse_pcap.py 가 그 이름으로 읽는다.
    """
    prompt = question + INSTR + (" " * pad)
    t0 = time.time()
    t_first = None
    answer_chars = 0      # 눈에 보이는 답 길이. 조건 무관 1이어야 길이 통제가 성립한다.
    thought_chars = 0     # 사고 '텍스트' 길이. display 기본값이 omitted 라 보통 0이다.
    sig_chars = 0         # 사고 서명 길이. Gemini 에서 누출의 정체였던 그 자리.
    sig_parts = 0
    chunk_count = 0       # 빈 keep-alive 청크가 바이트를 밀어올렸을 가능성 배제용 대조
    usage = None

    with client.messages.stream(
        model=model,
        max_tokens=max_tok,
        # Opus 5.5 는 thinking 을 끌 수 없고 adaptive 가 기본이다. 명시해서 판 간 차이를 없앤다.
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            t = time.time()
            chunk_count += 1
            et = str(_get(event, "type") or "")
            if et == "content_block_delta":
                d = _get(event, "delta")
                dt = str(_get(d, "type") or "")
                if dt == "text_delta":
                    txt = _get(d, "text") or ""
                    if txt:
                        # 첫 '내용 있는' 글자가 나온 시각이 TTFT 다. 공백은 안 센다.
                        if t_first is None and txt.strip():
                            t_first = t
                        answer_chars += len(txt)
                elif dt == "thinking_delta":
                    thought_chars += len(_get(d, "thinking") or "")
                elif dt == "signature_delta":
                    s = _get(d, "signature") or ""
                    if s:
                        sig_chars += len(s)
                        sig_parts += 1
            elif et == "message_delta":
                usage = _get(event, "usage") or usage
        final = stream.get_final_message()

    t_end = time.time()

    # 최종 메시지 쪽이 더 완전하다. 스트림 중간 usage 는 누적 전일 수 있다.
    final_usage = _get(final, "usage")
    if final_usage is not None:
        usage = final_usage

    # 서명이 delta 로 안 오고 최종 블록에만 실리는 판도 있다. 그때를 위해 한 번 더 훑는다.
    if sig_chars == 0:
        for b in (_get(final, "content") or []):
            if str(_get(b, "type") or "") == "thinking":
                s = _get(b, "signature") or ""
                if s:
                    sig_chars += len(s)
                    sig_parts += 1

    think_tok = _reasoning_tokens(usage)
    out_tok = _get(usage, "output_tokens")
    in_tok = _get(usage, "input_tokens")
    stop = _get(final, "stop_reason")

    return {
        "t_start": t0, "t_first_answer": t_first, "t_end": t_end,
        "app_ttft_ms": round((t_first - t0) * 1000, 1) if t_first else None,
        "app_total_ms": round((t_end - t0) * 1000, 1),
        "answer_chars": answer_chars,
        # 다른 러너와 이름을 맞춘다(parse_pcap 이 thoughts_tokens 로 읽는다).
        "thoughts_tokens": think_tok, "output_tokens": out_tok, "input_tokens": in_tok,
        "thought_chars": thought_chars, "had_thought": thought_chars > 0,
        "had_reasoning": think_tok is not None and think_tok > 0,
        "reasoning_chars": thought_chars,
        "sig_chars": sig_chars, "sig_parts": sig_parts,
        "chunk_count": chunk_count,
        "finish_reason": stop, "pad_chars": pad,
        # 추론 토큰 필드명이 아직 확정이 아니라 원본을 남긴다. 확인되면 _THINK_KEYS 를 고치고
        # 이 필드는 지워도 된다.
        "usage_raw": _usage_dict(usage),
        # 답이 한 글자도 안 나왔으면 추론이 max_tokens 까지 간 것이다. 분석에서 제외 대상.
        "truncated": answer_chars == 0 or stop == "max_tokens",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="out/anthropic_log_strict.jsonl")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--efforts", default=DEFAULT_EFFORTS,
                    help="쉼표 구분. Claude 는 low,medium,high,xhigh,max 만 있다"
                         "(none·minimal 없음, 모델에 따라 추론 off 자체가 불가)")
    ap.add_argument("--qset", default="v2", choices=sorted(QSETS))
    ap.add_argument("--qfile", default="",
                    help="선별 결과 JSON. 'good' 목록의 문항만 돈다. "
                         "provider 간 비교는 같은 문항이어야 성립한다")
    ap.add_argument("--sample", type=int, default=0,
                    help="갈래를 고르게 가로질러 N문항만")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--floor", type=int, default=8,
                    help="--sample 과 함께 쓴다. 갈래마다 최소 이만큼은 남긴다. "
                         "기본 8 은 갈래 19개와 곱해져 152문항 바닥을 만든다 — "
                         "작은 탐침에는 1 을 줘라.")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--max-tok", type=int, default=MAX_TOKENS)
    ap.add_argument("--seed", type=int, default=20261117)
    ap.add_argument("--no-shuffle", action="store_true",
                    help="섞지 않는다. 기본은 섞는다 — 조건 순서가 고정이면 망 상태 변화가 "
                         "조건 효과로 둔갑한다")
    ap.add_argument("--block-shuffle", action="store_true",
                    help="문항 단위 블록 셔플. 한 문항의 모든 조건을 연달아 찍고, "
                         "블록 순서와 블록 안 순서만 섞는다. 무작위화 블록 설계라 "
                         "조건과 시간이 엮이지 않으면서도, 도중에 끊겨도 찍힌 문항은 "
                         "조건이 다 모인다. 크레딧 상한이 있는 유료 provider 에서는 "
                         "사실상 필수다 — 전면 셔플은 끊기면 반쪽짜리 문항만 잔뜩 남는다.")
    # --- 예산 가드레일 -------------------------------------------------------
    # Anthropic 은 선불 크레딧이고 잔액이 바닥나면 콜이 그냥 실패한다. 추론 토큰량은
    # 문항·단계에 따라 수십 배로 튀어 사전 예측이 안 되므로(2026-11-18 실측: max 조건
    # 평균 2,503 토큰 vs low 266), 실제 usage 로 누적해 상한에서 스스로 멈춘다.
    # 멈춰도 그때까지의 로그는 남는다 — --block-shuffle 과 같이 쓰면 찍힌 문항은 온전하다.
    ap.add_argument("--price-in", type=float, default=None,
                    help="입력 단가($/1M). 주면 누적 비용을 표시한다. "
                         "opus-5-5=4, sonnet-5-5=2, haiku-5-5=0.10")
    ap.add_argument("--price-out", type=float, default=None,
                    help="출력 단가($/1M). 추론 토큰이 여기 포함된다. "
                         "opus-5-5=20, sonnet-5-5=10, haiku-5-5=0.50")
    ap.add_argument("--max-spend", type=float, default=None,
                    help="누적 비용이 이 금액($)을 넘으면 중단한다. 단가 2개와 함께 쓸 것")
    ap.add_argument("--dry-run", action="store_true",
                    help="콜을 한 개도 보내지 않고 문항수·콜수·실행순서·비용상한만 찍고 끝낸다. "
                         "유료 provider 에서는 본 실행 전에 항상 이걸 먼저 돌려라")
    ap.add_argument("--key-env", default="ANTHROPIC_API_KEY",
                    help="API 키가 든 환경변수 이름")
    ap.add_argument("--probe", action="store_true",
                    help="1콜만 돌려 usage 필드와 thinking 블록 구조를 보여주고 끝낸다. "
                         "캡처 전에 추론 토큰이 오는지(=Task B 가능 여부) 가리는 용도")
    args = ap.parse_args()

    key = os.getenv(args.key_env)
    if not key:
        raise SystemExit(f"{args.key_env} 없음. source ~/.llm_keys 했는지 확인하라")
    client = anthropic.Anthropic(api_key=key)

    conds = build_conditions(args.efforts)
    qset = QSETS[args.qset]
    qs, fams, keep = select_questions(args, qset)

    if args.probe:
        # 캡처 설계 전에 두 가지를 가린다.
        #   (1) usage 에 추론 토큰이 오는가 → Task B 라벨 가능 여부
        #   (2) thinking 블록에 signature 가 실리는가 → Gemini 와 같은 누출 경로 존재 여부
        cond, effort, pad = conds[-1]          # 가장 깊은 단계로 찔러야 추론이 확실히 돈다
        m = run_one(client, args.model, qs[0], effort, pad, max_tok=args.max_tok)
        print(f"모델 {args.model} / effort {effort}")
        print("usage_raw   :", json.dumps(m["usage_raw"], ensure_ascii=False))
        print("추론 토큰   :", m["thoughts_tokens"],
              "(None 이면 usage 에 안 온다 → Task B 라벨 불가)")
        print("답 글자수   :", m["answer_chars"], " 사고 텍스트:", m["thought_chars"])
        print("서명 글자수 :", m["sig_chars"], f"(파트 {m['sig_parts']}개)",
              "← 0 이 아니면 Gemini thoughtSignature 와 같은 누출 경로가 있다")
        print("청크        :", m["chunk_count"], " 종료:", m["finish_reason"])
        return

    trials = [(qi, cond, effort, pad, rep)
              for qi, _ in enumerate(qs)
              for cond, effort, pad in conds
              for rep in range(args.repeats)]
    if args.no_shuffle:
        pass
    elif args.block_shuffle:
        # 문항별로 묶어 블록을 만든다. 블록 안(조건·반복)만 섞고, 블록끼리도 섞는다.
        rng = random.Random(args.seed)
        blocks = {}
        for t in trials:
            blocks.setdefault(t[0], []).append(t)
        order = list(blocks)
        rng.shuffle(order)
        trials = []
        for qi in order:
            b = blocks[qi]
            rng.shuffle(b)
            trials.extend(b)
    else:
        random.Random(args.seed).shuffle(trials)

    logp = Path(args.log)
    logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(trials)
    pads = {c: p for c, _, p in conds}
    print(f"문항 {len(qs)}개 / 템플릿 {len(set(fams))}개")
    print(f"조건: {', '.join(c for c, _, _ in conds)}  패딩(공백수): {pads}")
    print(f"총 {total}콜")

    show_cost = args.price_in is not None and args.price_out is not None

    # --dry-run: 콜을 한 개도 안 보내고 계획만 보여주고 끝낸다. 크레딧이 한정된
    # provider 에서 "--sample 30 줬는데 760콜이 잡혔다"(2026-11-18) 같은 사고를
    # 돈 쓰기 전에 잡는 유일한 수단이다. 블록 셔플이 실제로 문항을 묶는지도 여기서 보인다.
    if args.dry_run:
        print("\n[dry-run] 콜을 보내지 않는다. 계획만 출력한다.")
        print(f"모델 {args.model} / 로그 {args.log}")
        print("앞 12콜 순서 (q번호 / 조건):")
        for i, (qi, cond, _e, _p, rep) in enumerate(trials[:12], 1):
            print(f"  [{i}] q{keep[qi]:<5d} {cond}")
        blk = {}
        for qi, *_ in trials:
            blk.setdefault(qi, 0)
            blk[qi] += 1
        print(f"문항당 콜 수: {sorted(set(blk.values()))} (전부 {len(conds) * args.repeats} 여야 정상)")
        if show_cost:
            # 추론 토큰량은 문항·단계마다 수십 배로 튀므로 이건 '최악치 상한'일 뿐이다.
            # 실제 비용은 거의 항상 이보다 훨씬 작다. 상한조차 예산을 넘으면 문항을 줄여라.
            hi = (total * (200 * args.price_in + args.max_tok * args.price_out)) / 1e6
            print(f"비용 상한(모든 콜이 max_tok {args.max_tok} 를 다 쓴 최악치): ${hi:.2f}")
            print("  ※ 실제는 이보다 훨씬 작다. 상한이 예산을 넘으면 --max-spend 를 꼭 걸어라.")
        return

    sum_in = sum_out = 0
    if args.max_spend is not None and not show_cost:
        raise SystemExit("--max-spend 를 쓰려면 --price-in 과 --price-out 을 같이 줘야 한다. "
                         "단가 없이는 누적 비용을 셀 수 없다.")
    # tcpdump 워밍업이 끝난 뒤 첫 콜이 나가도록 한 박자 쉰다.
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for i, (qi, cond, effort, pad, rep) in enumerate(trials, 1):
            try:
                m = run_one(client, args.model, qs[qi], effort, pad, max_tok=args.max_tok)
                m["error"] = None
            except Exception as e:
                # 실패를 조용히 넘기면 '쓸모없는 칸'과 '못 잰 칸'이 구분되지 않는다.
                m = {"error": f"{type(e).__name__}: {e}"}
            m.update({
                "idx": i, "order_idx": i,
                # 원본 리스트에서의 위치. 잘라낸 위치를 쓰면 문항을 되짚을 때 통째로 어긋난다.
                "q_idx": keep[qi],
                "family": fams[qi], "qset": args.qset,
                "condition": cond, "effort": effort, "rep": rep, "arm": 0,
                "expect_chars": 1,
                "complied": m.get("answer_chars") == 1,
                "service": "anthropic", "model": args.model,
                "shuffled": not args.no_shuffle,
            })
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
            f.flush()
            sum_in += m.get("input_tokens") or 0
            sum_out += m.get("output_tokens") or 0
            cost = ((sum_in * args.price_in + sum_out * args.price_out) / 1e6
                    if show_cost else None)
            tag = m.get("error") or (
                f"ttft={m.get('app_ttft_ms')}ms out={m.get('output_tokens')} "
                f"think={m.get('thoughts_tokens')} sig={m.get('sig_chars')} "
                f"chars={m.get('answer_chars')}/1"
                + ("" if m.get("complied") else " [불일치]")
                + (" [잘림]" if m.get("truncated") else ""))
            cost_tag = f" ${cost:.2f}" if cost is not None else ""
            print(f"[{i}/{total}] q{keep[qi]} {cond:14s} {tag}{cost_tag}")
            if args.max_spend is not None and cost is not None and cost > args.max_spend:
                print(f"\n[중단] 누적 ${cost:.3f} > 상한 ${args.max_spend:.2f}. "
                      f"{i}/{total} 콜에서 멈춘다. 여기까지의 로그는 그대로 쓸 수 있다.")
                break
            time.sleep(args.sleep)

    print(f"\n[done] 로그 -> {logp}")
    print(f"토큰: 입력 {sum_in:,} / 출력 {sum_out:,}")
    if show_cost:
        print(f"비용: ${(sum_in * args.price_in + sum_out * args.price_out) / 1e6:.3f}")
    print("→ 확인 1: answer_chars 가 조건 무관 1 인지(길이 통제 성공 여부)")
    print("→ 확인 2: truncated=true 건수(추론이 max_tokens 까지 간 콜 — 분석서 제외)")
    print("→ 확인 3: thoughts_tokens 가 None 뿐이면 Task B 라벨이 없다. usage_raw 를 볼 것")
    print("→ 확인 4: 파싱 후 CSV 에서 조건별 up_bytes 중앙값이 같은지(패딩 검증)")


if __name__ == "__main__":
    main()
