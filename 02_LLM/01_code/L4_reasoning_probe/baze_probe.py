"""baze_probe.py — 고려대 세종 BAZE 게이트웨이가 이 연구에 쓸 수 있는지 가린다.

왜 필요한가:
  게이트웨이는 OpenAI 호환이라고만 적혀 있다. 하지만 이 연구에 필요한 건 두 가지고,
  OpenAI 호환이라고 해서 둘 다 되는 게 아니다.
    (1) 응답 usage 에 **추론 토큰 수**가 실려 오는가 -> 없으면 정답 라벨이 없다.
        선별기도 캡처 러너도 전부 reasoning_tokens 를 읽는 구조다.
    (2) 추론 수준을 요청에서 **조절**할 수 있는가 -> 없으면 Configured 축이 없다.
        같은 프롬프트에 설정만 바꿔 쌍으로 비교하는 설계(Task A)가 통째로 무너진다.
  문서를 읽는 것보다 실제로 던져 보는 쪽이 확실하다. usage 를 통째로 찍는다.

  파라미터 이름도 모른다. provider 마다 다르다:
    OpenAI   : reasoning_effort="low"|"high"
    Gemini   : thinking_config.thinking_level
    호환 게이트웨이는 둘 중 하나를 받거나, extra_body 로 넘겨야 하거나, 무시한다.
  그래서 후보를 차례로 던져 보고 '무엇이 먹히는지'를 표로 보여준다.

입력: BAZE_API_KEY (없으면 GEMINI_API_KEY 로 대체)
출력: 설정별 usage 요약 + 판정
작성일: 2026-11-10
"""
import os
import sys
import json
import time
import statistics as st

from openai import OpenAI

BASE_URL = os.getenv("BAZE_BASE_URL", "https://api.baze.co/v1/gateway")
MODEL = os.getenv("BAZE_MODEL", "gemini-3.5-flash-lite")

key = os.getenv("BAZE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not key:
    raise SystemExit("BAZE_API_KEY 없음")

client = OpenAI(api_key=key, base_url=BASE_URL)

# 추론을 확실히 유발하는 문항. 쉬우면 어느 설정이든 0 이 나와서 구분이 안 된다.
PROMPT = ("체스판에서 나이트가 a1에서 h8까지 가는 최소 이동 수는? "
          "A) 4 B) 5 C) 6 D) 7\n\n정답 한 글자(A, B, C, D 중 하나)만 출력하라. "
          "설명·다른 말·문장부호 금지.")

# 후보 설정. (이름, kwargs) — 하나씩 던져 어느 것이 받아들여지는지 본다.
# 2026-11-10 1차 측정 결과: reasoning_effort 는 먹히고(1,041 -> 2,706 -> 9,382ms),
# extra_body 의 thinking_config 는 무시된다(928~1,210ms = 기준선). 그래서 먹히는 쪽의
# 사다리를 끝까지 재서 Task A 의 다중 분류가 몇 단계까지 성립하는지 본다.
# 단계 이름은 provider 마다 다르므로 실패해도 다음으로 넘어간다.
CANDIDATES = [("기본(설정 없음)", {})]
for _e in ["none", "minimal", "low", "medium", "high", "xhigh", "max"]:
    CANDIDATES.append((f"reasoning_effort={_e}", {"reasoning_effort": _e}))


def dig_reasoning(usage):
    """usage 객체 어디에 추론 토큰이 들어 있는지 뒤진다.

    위치가 provider/게이트웨이마다 다르다:
      OpenAI : usage.completion_tokens_details.reasoning_tokens
      Gemini 네이티브 : usage_metadata.thoughts_token_count
      호환 계층이 자기 식으로 담을 수도 있어 재귀로 'reason|thought|think' 를 찾는다.
    """
    try:
        d = usage.model_dump()
    except Exception:
        try:
            d = dict(usage)
        except Exception:
            return None, {}
    found = {}

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            name = ".".join(path).lower()
            if "reason" in name or "thought" in name or "think" in name:
                found[".".join(path)] = o

    walk(d, [])
    return d, found


# 반복 횟수. usage 에 추론 토큰이 안 와도 '추론을 실제로 돌았는지'는 시간으로 갈린다.
#   게이트웨이가 추론을 시키는데 보고만 안 하는 것   -> 설정에 따라 지연이 벌어진다(패킷 신호 살아 있음)
#   게이트웨이가 설정을 무시하고 추론을 안 시키는 것 -> 지연이 평평하다(Configured 축 없음)
# 한 번만 재면 망 잡음과 구분이 안 되므로 여러 번 재서 중앙값을 본다.
REPS = int(os.getenv("BAZE_REPS", "3"))

rows = []
raw_dump = None
for label, kw in CANDIDATES:
    lat, ctoks, txt, err = [], [], "", None
    for _ in range(REPS):
        t0 = time.time()
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": PROMPT}],
                max_completion_tokens=4096,
                **kw,
            )
            lat.append((time.time() - t0) * 1000.0)
            txt = (r.choices[0].message.content or "").strip()
            d, found = dig_reasoning(r.usage)
            ctoks.append(d.get("completion_tokens"))
            if raw_dump is None:
                raw_dump = d
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            break
        time.sleep(0.4)
    if err:
        rows.append((label, "실패", None, None, {}, err[:80]))
    else:
        d, found = dig_reasoning(r.usage)
        rows.append((label, "성공", st.median(lat), ctoks[-1], found, txt[:10]))

print(f"게이트웨이 {BASE_URL} / 모델 {MODEL} / 설정당 {REPS}회")
print()
print(f"{'설정':32s} {'결과':5s} {'지연중앙(ms)':>12s} {'출력토큰':>8s} {'추론토큰':>8s}  답/사유")
print("-" * 115)
for label, stt, ms, ct, found, note in rows:
    rt = next(iter(found.values())) if found else None
    msv = f"{ms:,.0f}" if ms is not None else "-"
    print(f"{label:32s} {stt:5s} {msv:>12s} {str(ct):>8s} {str(rt):>8s}  {note}")

print()
if raw_dump is not None:
    print("usage 원문(첫 성공 콜):")
    print(json.dumps(raw_dump, ensure_ascii=False, indent=1))
print()

ok_any = [r for r in rows if r[1] == "성공"]
with_reason = [r for r in rows if r[4]]
varied = {next(iter(r[4].values())) for r in with_reason}

# 지연 판정 — usage 에 추론 토큰이 없어도 여기서 신호 유무가 갈린다.
lats = {r[0]: r[2] for r in ok_any}
if len(lats) >= 2:
    lo, hi = min(lats.values()), max(lats.values())
    print("=== 지연 ===")
    print(f"  최소 {lo:,.0f}ms ({min(lats, key=lats.get)}) / "
          f"최대 {hi:,.0f}ms ({max(lats, key=lats.get)}) / 비 {hi / lo:.2f}배")
    # 참고: Gemini 직결 실측은 no_think 842ms vs high 1,637ms = 1.94배였다.
    if hi / lo >= 1.5:
        print("  -> 설정에 따라 지연이 뚜렷이 벌어진다. 추론은 실제로 돌고 있다(보고만 안 함).")
        print("     패킷 신호는 살아 있다. 라벨만 다른 경로로 받으면 캡처 대상이 된다.")
    else:
        print("  -> 지연이 평평하다. 게이트웨이가 추론 설정을 무시하는 것으로 보인다.")
        print("     Configured 축이 없으므로 Task A 를 이 게이트웨이로는 할 수 없다.")
    print()

# Task 별로 따로 판정한다. 둘의 라벨 출처가 다르기 때문이다.
#   Task A(Configured 탐지) : 라벨 = 내가 보낸 effort 값. usage 가 없어도 이미 안다.
#   Task B(Realized 회귀)   : 라벨 = usage 의 추론 토큰 수. 이게 없으면 성립하지 않는다.
# 초판에서 이걸 묶어 "usage 없으면 둘 다 불가"로 판정했는데 틀렸다.
print("=== 판정 ===")
if not ok_any:
    print("[실패] 콜 자체가 안 된다. Base URL·키·모델명을 확인하라.")
    sys.exit(1)

# 어떤 파라미터 이름이 먹히는지 — 기준선 대비 지연이 벌어지는 것만 유효하다.
base = next((r[2] for r in ok_any if r[0].startswith("기본")), None)
honored, ignored = [], []
for r in ok_any:
    if r[0].startswith("기본"):
        continue
    if base and r[2] >= base * 1.5:
        honored.append((r[0], r[2]))
    else:
        ignored.append((r[0], r[2]))

print("[Task A — Configured effort 탐지]")
if honored:
    print("  가능하다. 라벨은 usage 가 아니라 '내가 보낸 설정값' 이다.")
    print("  먹히는 파라미터: " + ", ".join(f"{k}({v:,.0f}ms)" for k, v in honored))
    if ignored:
        print("  무시되는 파라미터: " + ", ".join(f"{k}({v:,.0f}ms)" for k, v in ignored)
              + "  <- 캡처에 쓰면 전 조건이 같아져 라벨만 다른 쓰레기 데이터가 된다")
else:
    print("  불가능하다. 어떤 파라미터도 지연을 바꾸지 못한다 — 설정 축이 없다.")

print()
print("[Task B — Realized 추론 토큰 회귀]")
if not with_reason:
    print("  불가능하다. usage 에 추론 토큰이 없어 정답값을 만들 수 없다.")
    print("  -> Realized 라벨은 직결 API 에서 따로 받아야 한다(같은 모델·같은 문항).")
else:
    print(f"  가능하다. 필드: {sorted({k for r in with_reason for k in r[4]})}")
    if len(varied) <= 1:
        print("  단, 설정을 바꿔도 값이 변하지 않는다 — 실제로 추론이 도는지 확인하라.")
