"""
screen_qset.py — provider 공통 문항 선별기. "설정 간 추론 토큰 격차"로 문항을 고른다.

왜 필요한가
-----------
탐지 대상은 추론의 유무가 아니라 **양**이다. 모든 설정에서 20 토큰씩 쓰는 문항은
추론이 일어나긴 해도 설정(라벨)과 트래픽(신호)이 대응하지 않아 캡처해도 못 쓴다.

실측(2026-11-06, gpt-6-luna): 기존 30문항 중 격차 100 토큰 이상인 것이 **1개**
(q4 체스 나이트 254). 2위 q6(60), 3위 q1(51). 모델이 좋아지면서 나머지가 전부
1단계 계산으로 풀려버린 탓이다. 반면 같은 문항이 Gemini(121~634)·Groq(4~1262)
에서는 충분한 추론을 일으킨다 — 문항 난도가 provider·세대에 따라 다르게 작동한다.

그래서 **모든 provider 에서 동시에 격차가 큰 문항**만 골라 써야 교차 비교가 성립한다.
한쪽에만 맞는 문항으로 비교하면 provider 차이와 문항 차이가 엉킨다.

무엇을 재는가 (문항마다)
------------------------
  spread   : 설정을 바꿨을 때 추론 토큰의 max - min. 클수록 좋다.
  trunc    : 답이 한 글자도 안 나온 콜 수. 어려운 문항이 작은 모델에서 토큰 한계까지
             가면 여기 잡힌다(Groq 1차 q4 에서 4콜을 날린 그 사고). 0 이어야 쓸 수 있다.
  nonc     : 답이 한 글자를 넘은 콜 수. 지시는 'A~D 한 글자만' 인데 어긴 경우다.
             가치 판단 문항에서 모델이 답을 피하고 해명을 쓰면 여기 잡힌다. 길이 통제가
             깨지므로(답 길이가 조건별로 달라지면 그게 신호가 된다) 0 이어야 쓸 수 있다.

입력: 각 provider 의 API 키 환경변수
      openai=OPENAI_API_KEY / gemini=GEMINI_API_KEY|GOOGLE_API_KEY / groq=GROQ_API_KEY
출력: 표준출력 표 + out/screen_<provider>_<model>_<qset>.json

사용:
  python3 screen_qset.py --provider openai --model gpt-6-luna --qset hard
  python3 screen_qset.py --provider gemini --qset hard
  python3 screen_qset.py --combine out/screen_*.json      # 교집합 산출

비고: 선별은 패킷을 안 본다. 스트리밍도 안 쓴다(앱 지표만 필요). 캡처는 별도 스크립트.
작성일: 2026-11-06
"""
import os
import re
import json
import time
import glob
import argparse
from pathlib import Path

from groq_capture_run_strict import QUESTIONS as QUESTIONS_BASE, INSTR
from questions_hard import QUESTIONS_HARD

QSETS = {"base": QUESTIONS_BASE, "hard": QUESTIONS_HARD}

# 문항이 쓸 만하다고 보는 최소 격차(추론 토큰).
# 근거: 추론 N 토큰 ≈ 4N 바이트 응답 증가(Gemini 3차 실측에서 토큰당 약 3.9 바이트).
# 기준 응답이 1,400 바이트 안팎이므로 100 토큰 ≈ 400B ≈ 30% 변화라야 TLS 레코드
# 패딩과 망 잡음을 넘어 분류기가 집어낸다. 20 토큰(80B, 6%)으로는 묻힌다.
MIN_SPREAD = 100

# 추론이 폭주해 답을 못 낸 콜을 걸러내기 위한 상한. 조건별로 넉넉히 준다.
MAX_TOK = 8192

DEFAULT_EFFORTS = {
    # OpenAI: none 은 astra·6.1-sol 이 미지원이라 실패가 정상이다(표에 ERR 로 찍힌다).
    "openai": "none,low,medium,high,xhigh,max",
    # Gemini: thinking_level. no_think 는 thinking_config 자체를 빼는 조건이다.
    "gemini": "no_think,low,high",
    # Groq(gpt-oss): 추론 off 모드가 없어 3단 그라데이션뿐이다.
    "groq": "low,medium,high",
}

DEFAULT_MODELS = {
    "openai": "gpt-6-luna",
    "gemini": "gemini-3.5-flash-lite",
    "groq": "openai/gpt-oss-20b",
}


def _get(obj, name):
    """객체 속성이든 dict 키든 같은 방식으로 꺼낸다(SDK 판마다 달라서)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


# ── provider 별 1콜 ────────────────────────────────────────────────────────
# 전부 (추론토큰, 답글자수) 를 돌려준다. 실패하면 예외를 그대로 올린다.

def _call_openai(client, model, prompt, effort):
    """Responses API. chat 은 max 를 안 받고 astra 에서 범위도 좁아 이쪽으로 통일했다."""
    r = client.responses.create(
        model=model, input=[{"role": "user", "content": prompt}],
        reasoning={"effort": effort}, max_output_tokens=MAX_TOK)
    rt = _get(_get(r.usage, "output_tokens_details"), "reasoning_tokens")
    txt = getattr(r, "output_text", None) or ""
    return (rt or 0), len(txt.strip())


def _call_gemini(client, model, prompt, effort):
    """thinking_level 로 깊이를 준다. no_think 는 thinking_config 를 아예 안 보낸다."""
    from google.genai import types
    kw = {"max_output_tokens": MAX_TOK}
    if effort != "no_think":
        kw["thinking_config"] = types.ThinkingConfig(thinking_level=effort)
    r = client.models.generate_content(
        model=model, contents=prompt, config=types.GenerateContentConfig(**kw))
    um = getattr(r, "usage_metadata", None)
    rt = _get(um, "thoughts_token_count")
    txt = getattr(r, "text", None) or ""
    return (rt or 0), len(txt.strip())


def _call_groq(client, model, prompt, effort):
    """OpenAI 호환. reasoning_format='hidden' 으로 추론을 답 스트림에 안 싣는다."""
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        reasoning_effort=effort, reasoning_format="hidden",
        max_completion_tokens=MAX_TOK)
    u = r.usage
    rt = _get(_get(u, "completion_tokens_details"), "reasoning_tokens")
    txt = (r.choices[0].message.content or "") if r.choices else ""
    return (rt or 0), len(txt.strip())


def make_client(provider):
    """provider 별 클라이언트. 키가 없으면 여기서 멈춘다."""
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY 없음")
        from openai import OpenAI
        return OpenAI(), _call_openai
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise SystemExit("GEMINI_API_KEY 없음")
        from google import genai
        return genai.Client(api_key=key), _call_gemini
    if provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            raise SystemExit("GROQ_API_KEY 없음")
        from groq import Groq
        return Groq(api_key=os.getenv("GROQ_API_KEY")), _call_groq
    raise SystemExit(f"모르는 provider: {provider}")


def screen(provider, model, qset_name, efforts, sleep, limit=0):
    """문항 × 설정을 돌려 문항별 격차를 잰다."""
    client, call = make_client(provider)
    qs = QSETS[qset_name]
    if limit:
        qs = qs[:limit]

    print(f"\n=== {provider} / {model} / qset={qset_name} / {','.join(efforts)} ===")
    print(f"{'q':>3}" + "".join(f"{e:>9}" for e in efforts)
          + f"{'격차':>7}{'잘림':>5}{'불응':>5}  문항")

    rows = []
    for qi, q in enumerate(qs):
        prompt = q + INSTR
        vals, trunc, nonc = [], 0, 0
        for effort in efforts:
            try:
                rt, nchars = call(client, model, prompt, effort)
                vals.append(rt)
                # 답이 한 글자도 없으면 추론이 한계까지 간 것이다. 분석에서 제외 대상.
                if nchars == 0:
                    trunc += 1
                # 한 글자를 넘으면 지시 불응이다. 가치 판단 문항에서 모델이 답을 피하고
                # 해명을 쓰면 여기 걸린다. 답 길이가 조건별로 달라지면 그 자체가 신호가
                # 되어 길이 통제가 깨지므로 쓸 수 없는 문항이다.
                elif nchars > 1:
                    nonc += 1
            except Exception:
                # 지원 안 하는 설정(astra 의 none 등)은 격차 계산에서 빼야 한다.
                vals.append(None)
            time.sleep(sleep)
        got = [v for v in vals if v is not None]
        spread = (max(got) - min(got)) if got else 0
        rows.append({"q": qi, "spread": spread, "trunc": trunc, "nonc": nonc,
                     "vals": vals, "text": q})
        cells = "".join(f"{('—' if v is None else v):>9}" for v in vals)
        print(f"{qi:>3}{cells}{spread:>7}{trunc:>5}{nonc:>5}  {q[:40]}")

    good = [r["q"] for r in rows
            if r["spread"] >= MIN_SPREAD and r["trunc"] == 0 and r["nonc"] == 0]
    print(f"\n격차 {MIN_SPREAD}+ · 잘림 0 · 불응 0: {len(good)}/{len(rows)}")
    print(f"  쓸 문항: {good}")
    top = sorted(rows, key=lambda r: -r["spread"])[:10]
    print("  격차 상위: " + ", ".join(f"q{r['q']}({r['spread']})" for r in top))
    if any(r["trunc"] for r in rows):
        bad = [r["q"] for r in rows if r["trunc"]]
        print(f"  ⚠️ 잘린 문항(이 모델엔 너무 어렵다): {bad}")
    if any(r["nonc"] for r in rows):
        bad = [r["q"] for r in rows if r["nonc"]]
        print(f"  ⚠️ 불응 문항(답을 피하거나 해명을 씀 — 길이 통제 깨짐): {bad}")

    outp = Path("out") / f"screen_{provider}_{_slug(model)}_{qset_name}.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(
        {"provider": provider, "model": model, "qset": qset_name,
         "efforts": efforts, "min_spread": MIN_SPREAD,
         "good": good, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> {outp}")
    return good


def _slug(s):
    """파일명에 쓸 수 있게 모델 id 를 눕힌다(슬래시·점이 들어가므로)."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", s)


def combine(paths):
    """여러 선별 결과의 **교집합**을 낸다. 이게 최종 캡처용 문항 세트다.

    교집합을 쓰는 이유 — 한 provider 에만 맞는 문항으로 비교하면 provider 차이와
    문항 차이가 엉켜 아무 결론도 못 낸다. 모두에서 격차가 크고 아무도 잘리지 않는
    문항만 남겨야 "같은 문항·같은 프로토콜"이라고 말할 수 있다.
    """
    sets, metas = [], []
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        sets.append(set(d["good"]))
        metas.append((d["provider"], d["model"], d["qset"], len(d["good"])))
    if not sets:
        raise SystemExit("합칠 파일이 없다")

    qsets = {m[2] for m in metas}
    if len(qsets) > 1:
        raise SystemExit(f"문항 세트가 섞였다: {qsets}. 같은 qset 끼리만 합칠 것.")

    print("입력:")
    for prov, mdl, qs, n in metas:
        print(f"  {prov:8s} {mdl:24s} {qs:5s} 통과 {n}")
    inter = sorted(set.intersection(*sets))
    union = sorted(set.union(*sets))
    print(f"\n교집합 {len(inter)}문항: {inter}")
    print(f"합집합 {len(union)}문항: {union}")

    # 어느 provider 가 병목인지 보여준다. 거기 맞춰 문항을 보강해야 한다.
    for (prov, mdl, _qs, _n), s in zip(metas, sets):
        drop = sorted(set(union) - s)
        if drop:
            print(f"  {prov}/{mdl} 에서 탈락: {drop}")

    if len(inter) < 10:
        print(f"\n⚠️ 교집합이 {len(inter)}개뿐이다. 질문별 교차검증에서 독립 표본은 사실상")
        print("   문항 수이므로 이대로는 일반화를 주장할 수 없다. 병목 provider 에 맞는")
        print("   난도의 문항을 보강할 것.")
    return inter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=sorted(DEFAULT_MODELS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--qset", default="hard", choices=sorted(QSETS))
    ap.add_argument("--efforts", default=None,
                    help="provider 기본값을 쓰려면 비워둘 것")
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=0, help="앞 N문항만(연습용)")
    ap.add_argument("--combine", nargs="+", default=None,
                    help="선별 결과 json 들의 교집합을 낸다")
    args = ap.parse_args()

    if args.combine:
        paths = []
        for pat in args.combine:
            paths += sorted(glob.glob(pat)) or [pat]
        combine(paths)
        return

    if not args.provider:
        raise SystemExit("--provider 또는 --combine 중 하나는 필요하다")
    model = args.model or DEFAULT_MODELS[args.provider]
    efforts = [e.strip() for e in
               (args.efforts or DEFAULT_EFFORTS[args.provider]).split(",") if e.strip()]
    screen(args.provider, model, args.qset, efforts, args.sleep, args.limit)


if __name__ == "__main__":
    main()
