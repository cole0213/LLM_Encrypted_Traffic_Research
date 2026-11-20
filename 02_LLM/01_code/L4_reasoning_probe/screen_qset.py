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
from questions_all import QUESTIONS_V2_ALL, FAMILIES_V2_ALL, ANSWERS_V2_ALL
# 2026-11-17 추가. 경량 모델이 왜 추론을 더 쓰는지(능력 차이 vs 예산 매핑)를
# 가르는 대조군. 한 걸음이면 끝나는 문항만 들었다.
from questions_trivial import (QUESTIONS_TRIVIAL, FAMILIES_TRIVIAL,
                               ANSWERS_TRIVIAL)

QSETS = {"base": QUESTIONS_BASE, "hard": QUESTIONS_HARD, "v2": QUESTIONS_V2_ALL,
         "trivial": QUESTIONS_TRIVIAL}

# 문항 세트별 템플릿 id. 없는 세트는 None — 그때는 문항 하나가 곧 클러스터로 취급된다.
# v2 는 한 템플릿에서 변형이 여럿 나오므로 선별 결과를 템플릿 단위로도 집계해야
# '한 템플릿만 잘 돼서 통과 수가 부풀어 보이는' 착시를 피할 수 있다.
QSET_FAMILIES = {"base": None, "hard": None, "v2": FAMILIES_V2_ALL,
                 "trivial": FAMILIES_TRIVIAL}

# 세트별 정답 글자. 없는 세트는 None — 그때는 정답률을 못 낸다.
# v2 의 "정답 없는 갈래"(딜레마·페르미 등)는 원소가 None 이라 그 문항만 집계에서 빠진다.
# 2026-11-17 추가. 그 전까지 선별기는 답 글자를 버려서, 모델이 추론을 안 쓰고도
# 맞혔는지("성능이 좋아 생략")와 그냥 틀렸는지를 구분할 수 없었다.
QSET_ANSWERS = {"base": None, "hard": None, "v2": ANSWERS_V2_ALL,
                "trivial": ANSWERS_TRIVIAL}

# 문항이 쓸 만하다고 보는 최소 격차(추론 토큰).
# 근거: 추론 N 토큰 ≈ 4N 바이트 응답 증가(Gemini 3차 실측에서 토큰당 약 3.9 바이트).
# 기준 응답이 1,400 바이트 안팎이므로 100 토큰 ≈ 400B ≈ 30% 변화라야 TLS 레코드
# 패딩과 망 잡음을 넘어 분류기가 집어낸다. 20 토큰(80B, 6%)으로는 묻힌다.
MIN_SPREAD = 100

# 추론이 폭주해 답을 못 낸 콜을 걸러내기 위한 상한. 조건별로 넉넉히 준다.
MAX_TOK = 8192

# 호출 실패 재시도. 무료 등급 gemini 는 분당 한도에 걸려 연속으로 몇 콜씩 죽는다.
# 재시도 없이 None 으로 넘기면 그 문항이 '격차 없는 문항'으로 잘못 탈락한다.
MAX_RETRY = 3
RETRY_WAIT = 4.0      # 초. 재시도마다 2배씩 늘린다(4 → 8 → 16).

# 연속 실패 중단. 일당 할당량이 바닥나면 재시도를 몇 번 하든 전부 실패한다.
# 2026-11-10 Gemini 선별이 q135 부근에서 할당량에 걸렸는데, 중단 조건이 없어
# 남은 680문항을 백오프만 쓰며 6.8시간 태울 참이었다. 그래서 끊는다.
DEAD_AFTER = 8        # 이만큼 연속으로 '한 설정도 못 잰' 문항이 나오면 중단

DEFAULT_EFFORTS = {
    # OpenAI: none 은 astra·6.1-sol 이 미지원이라 실패가 정상이다(표에 ERR 로 찍힌다).
    "openai": "none,low,medium,high,xhigh,max",
    # Gemini: thinking_level. no_think 는 thinking_config 자체를 빼는 조건이다.
    "gemini": "no_think,low,high",
    # Groq(gpt-oss): 추론 off 모드가 없어 3단 그라데이션뿐이다.
    "groq": "low,medium,high",
    # Anthropic: output_config.effort 5단. Opus 5.5 는 추론을 끌 수 없어
    #   none 에 해당하는 조건이 아예 없다.
    "anthropic": "low,medium,high,xhigh,max",
}

DEFAULT_MODELS = {
    "openai": "gpt-6-luna",
    "gemini": "gemini-3.5-flash-lite",
    "groq": "openai/gpt-oss-20b",
    "anthropic": "claude-opus-5-5",
}


def _get(obj, name):
    """객체 속성이든 dict 키든 같은 방식으로 꺼낸다(SDK 판마다 달라서)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _letter(txt):
    """응답에서 답 글자(A~D)를 뽑는다. 못 찾으면 None.

    INSTR 이 한 글자만 내라고 못박았지만 모델이 어기는 일이 있다(nonc 로 세는 그것).
    그때도 첫 글자를 집어 두면 '불응했지만 답은 맞았다'를 따로 볼 수 있다.
    """
    m = re.search(r"[A-Da-d]", txt or "")
    return m.group(0).upper() if m else None


# ── provider 별 1콜 ────────────────────────────────────────────────────────
# 전부 (추론토큰, 답글자수, 답글자) 를 돌려준다. 실패하면 예외를 그대로 올린다.

def _call_openai(client, model, prompt, effort):
    """Responses API. chat 은 max 를 안 받고 astra 에서 범위도 좁아 이쪽으로 통일했다."""
    r = client.responses.create(
        model=model, input=[{"role": "user", "content": prompt}],
        reasoning={"effort": effort}, max_output_tokens=MAX_TOK)
    rt = _get(_get(r.usage, "output_tokens_details"), "reasoning_tokens")
    txt = getattr(r, "output_text", None) or ""
    return (rt or 0), len(txt.strip()), _letter(txt)


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
    return (rt or 0), len(txt.strip()), _letter(txt)


def _call_anthropic(client, model, prompt, effort):
    """Messages API. 추론 단계는 reasoning_effort 가 아니라 output_config.effort 다.

    thinking 은 Opus 5.5 에서 끌 수 없고 adaptive 가 기본 — 판 간 차이를 없애려고
    명시한다. usage 의 추론 토큰 필드명이 문서에 없어서 후보를 전부 훑는다.
    후보에 하나도 없으면 None 을 올려 호출부가 '라벨 없음'으로 처리하게 한다.
    """
    r = client.messages.create(
        model=model, max_tokens=MAX_TOK,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": prompt}])
    u = r.usage
    rt = None
    for k in ("thinking_tokens", "reasoning_tokens", "thought_tokens",
              "output_thinking_tokens", "reasoning_output_tokens"):
        v = _get(u, k)
        if v is not None:
            rt = v
            break
    # 본문 텍스트만 모은다. thinking 블록은 답이 아니다.
    txt = "".join(_get(b, "text") or "" for b in (r.content or [])
                  if str(_get(b, "type")) == "text")
    return (rt or 0), len(txt.strip()), _letter(txt)


def _call_groq(client, model, prompt, effort):
    """OpenAI 호환. reasoning_format='hidden' 으로 추론을 답 스트림에 안 싣는다."""
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        reasoning_effort=effort, reasoning_format="hidden",
        max_completion_tokens=MAX_TOK)
    u = r.usage
    rt = _get(_get(u, "completion_tokens_details"), "reasoning_tokens")
    txt = (r.choices[0].message.content or "") if r.choices else ""
    return (rt or 0), len(txt.strip()), _letter(txt)


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
    if provider == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY 없음")
        import anthropic
        return anthropic.Anthropic(), _call_anthropic
    raise SystemExit(f"모르는 provider: {provider}")


def _group_of(fam):
    """템플릿 id 에서 갈래 이름을 뽑는다. fermi_007 -> fermi, knight_path -> knight_path.

    페르미·딜레마는 문항 하나하나가 템플릿이라 id 끝에 일련번호가 붙는다(fermi_007).
    통과율은 갈래 단위로 봐야 뜻이 있으므로 그 번호를 떼고 묶는다.
    """
    i = fam.rfind("_")
    if i > 0 and fam[i + 1:].isdigit():
        return fam[:i]
    return fam


def _pick(qset_name, limit, sample, families="", skip_done=""):
    """돌릴 문항을 고른다. 반환은 (원본 q_idx, 문항) 쌍이다.

    q_idx 는 반드시 **원본 리스트에서의 위치**여야 한다. 잘라낸 리스트의 위치를 쓰면
    FAMILIES 와 어긋나 템플릿 집계와 교집합이 통째로 틀어진다.

    --limit    : 앞에서 N개. 세트 앞쪽이 한 갈래로 쏠려 있으면 그 갈래만 보게 된다.
    --sample   : 템플릿을 번갈아 돌며 N개. 콜마다 돈이 나가는 provider 에서 전체
                 그림을 싸게 보려면 이쪽을 쓴다.
    --families : 특정 템플릿만. 쉼표로 여러 개. 접두사 매칭이라 'fermi' 로
                 fermi_000~fermi_239 가 전부 잡힌다.
    --skip-done: 이미 돌린 선별 JSON 경로. 거기서 측정된 문항은 뺀다.
                 할당량에 걸려 중간에 끊겼을 때 이어서 돌리는 용도다.
                 (못 잰 문항 incomplete 은 다시 돌린다 — 그게 재시도의 요점이다)

    적용 순서: families 로 거른 뒤 skip_done 을 빼고, 그다음 sample/limit.
    통과율이 이미 높다고 확인된 갈래를 또 돌리는 건 낭비다 — 2026-11-10 측정에서
    솔버 갈래는 92~100% 통과라 선별이 캡처보다 비쌌다. 모르는 갈래부터 재라.
    """
    qs = QSETS[qset_name]
    idx = list(range(len(qs)))
    fam_all = QSET_FAMILIES.get(qset_name)

    if families:
        if not fam_all:
            raise SystemExit(f"--families 는 템플릿이 있는 세트에만 쓴다(qset={qset_name})")
        pats = [p.strip() for p in families.split(",") if p.strip()]
        idx = [i for i in idx if any(fam_all[i].startswith(p) for p in pats)]
        if not idx:
            raise SystemExit(f"--families {families} 에 맞는 문항이 없다")
        print(f"템플릿 필터: {families} -> {len(idx)}문항")

    if skip_done:
        prev = json.loads(Path(skip_done).read_text(encoding="utf-8"))
        # 못 잰 문항(incomplete)은 빼지 않는다. 그게 다시 돌려야 할 것들이다.
        bad = set(prev.get("incomplete") or [])
        done = {r["q"] for r in prev.get("rows", [])} - bad
        before = len(idx)
        idx = [i for i in idx if i not in done]
        print(f"이미 측정됨 제외: {skip_done} -> {before} - {before - len(idx)} = {len(idx)}문항")
    if sample and sample < len(idx):
        fams = fam_all
        if fams:
            buckets = {}
            for i in idx:
                buckets.setdefault(fams[i], []).append(i)
            # 템플릿 단위로만 돌면 안 된다. 갈래마다 템플릿 수가 극단적으로 다르다:
            #   fermi 는 템플릿 240개(문항 1개씩), alibi 는 템플릿 1개(문항 25개).
            # 템플릿을 고르게 집으면 fermi 가 표본을 독식하고 alibi·truth_count 같은
            # 1템플릿 갈래는 0개가 된다(2026-11-10 실제로 그랬다).
            # 재려는 것은 '갈래별 통과율'이므로 갈래를 먼저 균등하게 나눈다.
            # 3단: 갈래 -> 그 갈래의 템플릿 -> 그 템플릿의 문항.
            groups = {}
            for f, ids in buckets.items():
                groups.setdefault(_group_of(f), {})[f] = list(ids)
            picked = []
            gkeys = sorted(groups)
            # 갈래를 한 바퀴씩 돌며 하나씩 집는다. 갈래 안에서도 템플릿을 번갈아
            # 집어 한 템플릿의 변형만 쏠리지 않게 한다.
            cursor = {g: 0 for g in gkeys}
            while len(picked) < sample:
                moved = False
                for g in gkeys:
                    if len(picked) >= sample:
                        break
                    tks = sorted(groups[g])
                    if not tks:
                        continue
                    # 이 갈래에서 다음 차례 템플릿을 고른다(비어 있으면 건너뛴다).
                    for _ in range(len(tks)):
                        t = tks[cursor[g] % len(tks)]
                        cursor[g] += 1
                        if groups[g][t]:
                            picked.append(groups[g][t].pop(0))
                            moved = True
                            break
                if not moved:        # 모든 갈래가 바닥났다
                    break
            idx = sorted(picked)
        else:
            step = max(1, len(idx) // sample)
            idx = idx[::step][:sample]
    elif limit:
        idx = idx[:limit]
    return [(i, qs[i]) for i in idx]


def _write_result(outp, provider, model, qset_name, efforts, fams,
                  rows, good, incomplete, err_log, stopped_early):
    """선별 결과를 파일에 쓴다. 문항마다 호출해 중간에 죽어도 남게 한다.

    왜 매번 쓰나: 끝에 한 번만 쓰면 몇 시간치 호출이 중단 한 번에 사라진다.
    파일이 작고(수백 KB) 로컬 디스크라 문항당 한 번 써도 비용이 무시할 만하다.
    """
    outp.parent.mkdir(parents=True, exist_ok=True)
    tmp = outp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(
        {"provider": provider, "model": model, "qset": qset_name,
         "efforts": efforts, "min_spread": MIN_SPREAD,
         "families": fams, "good": good, "rows": rows,
         "incomplete": incomplete,
         "errors": [{"q": a, "effort": b, "err": c} for a, b, c in err_log],
         # 중간에 끊겼는지. True 면 '안 돌린 문항'이지 '격차 없는 문항'이 아니다.
         "stopped_early": stopped_early,
         "n_done": len(rows)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    # 원자적 교체. 쓰는 도중에 죽어도 기존 파일이 깨지지 않는다.
    tmp.replace(outp)


def screen(provider, model, qset_name, efforts, sleep, limit=0, sample=0,
           families="", skip_done=""):
    """문항 × 설정을 돌려 문항별 격차를 잰다."""
    client, call = make_client(provider)
    pairs = _pick(qset_name, limit, sample, families, skip_done)

    print(f"\n=== {provider} / {model} / qset={qset_name} / {','.join(efforts)} ===")
    print(f"문항 {len(pairs)}개 x 설정 {len(efforts)}개 = {len(pairs) * len(efforts)}콜")
    print(f"{'q':>4}" + "".join(f"{e:>9}" for e in efforts)
          + f"{'격차':>7}{'잘림':>5}{'불응':>5}  문항")

    rows = []
    err_log = []          # (q_idx, effort, 사유) — 끝에 요약해서 보여준다
    dead_streak = 0       # 한 설정도 못 잰 문항이 연달아 몇 개 나왔나
    stopped_early = False
    # 템플릿 목록은 루프 안의 증분 저장에서도 쓴다. 루프 뒤에서 정의하면
    # 첫 문항을 저장할 때 UnboundLocalError 가 난다.
    fams = QSET_FAMILIES.get(qset_name)
    golds = QSET_ANSWERS.get(qset_name)
    outp = Path("out") / f"screen_{provider}_{_slug(model)}_{qset_name}.json"
    # 아예 지원되지 않는 설정(astra 의 none 등)은 몇 번을 눌러도 실패한다.
    # 그런 설정에 백오프를 다 쓰면 문항마다 12초씩 날린다(600문항이면 2시간).
    # 그래서 재시도를 끄되, 조건을 좁힌다: **한 번도 성공한 적 없는** 설정만 끈다.
    # 레이트리밋은 세 설정을 동시에 죽이므로 '연속 실패'만 보면 멀쩡한 설정까지
    # 미지원으로 찍혀 남은 run 내내 재시도가 사라진다.
    fail_streak = {e: 0 for e in efforts}
    ok_count = {e: 0 for e in efforts}
    dead_efforts = set()
    for qi, q in pairs:
        prompt = q + INSTR
        vals, answers, trunc, nonc = [], [], 0, 0
        for effort in efforts:
            rt = nchars = ans = None
            last_err = None
            # 호출 실패를 조용히 None 으로 넘기면 안 된다. 2026-11-09 gemini 선별에서
            # q36-41, q47-50 이 통째로 None 이 되어 격차 0 으로 탈락했는데, 끊긴 자리가
            # 연속 구간인 것부터가 문항 문제가 아니라 레이트리밋이라는 증거였다.
            # 에러를 삼키면 '쓸모없는 문항'과 '못 잰 문항'이 구분되지 않는다.
            # 그래서 재시도하고, 끝내 실패하면 사유를 남긴다.
            tries = 1 if effort in dead_efforts else MAX_RETRY
            for attempt in range(tries):
                try:
                    rt, nchars, ans = call(client, model, prompt, effort)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    if attempt < tries - 1:
                        # 지수 백오프. 레이트리밋은 조금 기다리면 풀린다.
                        time.sleep(RETRY_WAIT * (2 ** attempt))
            if last_err is not None:
                # 지원 안 하는 설정(astra 의 none 등)도 여기로 온다. 격차 계산에서 뺀다.
                vals.append(None)
                answers.append(None)
                err_log.append((qi, effort, f"{type(last_err).__name__}: {last_err}"))
                fail_streak[effort] += 1
                if (fail_streak[effort] >= 2 and ok_count[effort] == 0
                        and effort not in dead_efforts):
                    dead_efforts.add(effort)
                    print(f"     [안내] '{effort}' 설정이 연속 2회 실패 — "
                          f"미지원으로 보고 이후 재시도 생략")
            else:
                fail_streak[effort] = 0
                ok_count[effort] += 1
                vals.append(rt)
                answers.append(ans)
                # 답이 한 글자도 없으면 추론이 한계까지 간 것이다. 분석에서 제외 대상.
                if nchars == 0:
                    trunc += 1
                # 한 글자를 넘으면 지시 불응이다. 가치 판단 문항에서 모델이 답을 피하고
                # 해명을 쓰면 여기 걸린다. 답 길이가 조건별로 달라지면 그 자체가 신호가
                # 되어 길이 통제가 깨지므로 쓸 수 없는 문항이다.
                elif nchars > 1:
                    nonc += 1
            time.sleep(sleep)
        got = [v for v in vals if v is not None]
        spread = (max(got) - min(got)) if got else 0
        gold = golds[qi] if golds else None
        rows.append({"q": qi, "spread": spread, "trunc": trunc, "nonc": nonc,
                     "vals": vals, "ans": answers, "gold": gold, "text": q})
        cells = "".join(f"{('—' if v is None else v):>9}" for v in vals)
        print(f"{qi:>4}{cells}{spread:>7}{trunc:>5}{nonc:>5}  {q[:40]}", flush=True)

        # 문항마다 저장한다. 끝에 한 번만 쓰면 중단 시 전부 날아간다.
        _inc = [r["q"] for r in rows if any(v is None for v in r["vals"])]
        _good = [r["q"] for r in rows
                 if r["spread"] >= MIN_SPREAD and r["trunc"] == 0
                 and r["nonc"] == 0 and r["q"] not in _inc]
        _write_result(outp, provider, model, qset_name, efforts, fams,
                      rows, _good, _inc, err_log, stopped_early=True)

        # 한 설정도 못 잰 문항이 연달아 나오면 할당량이 바닥난 것이다.
        # 재시도를 아무리 해도 안 되므로 끊는다. 남은 문항을 백오프로만 태우면
        # 몇 시간이 날아가고, 그 문항들이 '격차 없음'으로 오해될 수도 있다.
        if all(v is None for v in vals):
            dead_streak += 1
            if dead_streak >= DEAD_AFTER:
                print(f"\n  [중단] {DEAD_AFTER}문항 연속으로 한 설정도 못 쟀다. "
                      f"할당량 소진으로 보고 멈춘다.")
                print(f"         q{qi} 까지 {len(rows)}문항 측정됨. 결과는 저장돼 있다.")
                stopped_early = True
                break
        else:
            dead_streak = 0

    # 설정을 하나라도 못 잰 행은 격차를 믿을 수 없다. 살아남은 값으로만 min/max 를
    # 재면 빠진 설정만큼 격차가 작게 나와서 '격차 작은 문항'으로 둔갑한다. 따로 센다.
    incomplete = [r["q"] for r in rows if any(v is None for v in r["vals"])]
    good = [r["q"] for r in rows
            if r["spread"] >= MIN_SPREAD and r["trunc"] == 0 and r["nonc"] == 0
            and r["q"] not in incomplete]
    if err_log:
        from collections import Counter as _C
        n_call = len(pairs) * len(efforts)
        kinds = _C(e[2].split(":")[0] for e in err_log)
        print(f"\n  [경고] 호출 실패 {len(err_log)}건 / {n_call}콜 "
              f"({100.0 * len(err_log) / n_call:.1f}%)")
        for k, c in kinds.most_common():
            print(f"     {k}: {c}건")
        print("     처음 3건: " + " | ".join(
            f"q{a}/{b} {c[:70]}" for a, b, c in err_log[:3]))
        print(f"     못 잰 문항 {len(incomplete)}개 — '격차 작음'이 아니라 '못 쟀음'이다: "
              f"{incomplete[:20]}")
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

    # 템플릿 단위 집계. 한 템플릿의 변형 25개가 통째로 통과하면 문항 수는 25 늘지만
    # 독립 표본은 1 늘 뿐이다. 두 수를 같이 봐야 세트가 실제로 얼마나 넓은지 안다.
    if fams:
        from collections import Counter
        per = Counter(fams[r["q"]] for r in rows)
        hit = Counter(fams[q] for q in good)
        print(f"\n  템플릿 {len(hit)}/{len(per)}개에서 통과 문항이 나왔다")
        for f, c in sorted(hit.items(), key=lambda z: -z[1])[:12]:
            print(f"    {f:18s} {c:3d}/{per[f]}")
        dead = sorted(f for f in per if f not in hit)
        if dead:
            shown = ", ".join(dead[:10]) + (" ..." if len(dead) > 10 else "")
            print(f"    통과 0인 템플릿 {len(dead)}개: {shown}")

    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(
        {"provider": provider, "model": model, "qset": qset_name,
         "efforts": efforts, "min_spread": MIN_SPREAD,
         "families": fams, "good": good, "rows": rows,
         # 못 잰 문항을 기록해 둔다. 다음에 그 문항만 다시 돌리면 된다.
         "incomplete": incomplete,
         "errors": [{"q": a, "effort": b, "err": c} for a, b, c in err_log]},
        ensure_ascii=False, indent=1), encoding="utf-8")
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
    ap.add_argument("--limit", type=int, default=0, help="앞 N문항만(배선 확인용)")
    ap.add_argument("--sample", type=int, default=0,
                    help="템플릿을 고르게 가로지르며 N문항만(비용 드는 provider 용)")
    ap.add_argument("--families", default="",
                    help="특정 템플릿만 (쉼표 구분, 접두사 매칭). 예) fermi,dilemma")
    ap.add_argument("--skip-done", default="",
                    help="이미 돌린 선별 JSON. 거기서 측정된 문항은 뺀다(이어 돌리기)")
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
    screen(args.provider, model, args.qset, efforts, args.sleep,
           args.limit, args.sample, args.families, args.skip_done)


if __name__ == "__main__":
    main()
