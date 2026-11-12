"""문항 세트 v2 — 증거 기반 추론 (솔버가 정답을 계산).

목적:
  "진술 몇 개가 주어지고 그중 일부만 참일 때 진실을 역추적하는" 유형을 생성한다.
  2026-11-08 luna 선별에서 이 갈래의 설정 간 추론 격차 중앙값이 811로 가장 높았다
  (페르미 516, 딜레마 276, 논리 146, 탐색 106, 산술 59).

왜 비싼가:
  가정을 하나 세우고 끝까지 밀어본 뒤, 모순이 나오면 되돌아와 다음 가정을 민다.
  후보가 n개면 최악 n번 밀어야 하고, 각 밀기마다 모든 진술을 다시 맞춰봐야 한다.
  절차가 정해진 계산과 달리 '어디까지 검산할지'에 끝이 없어 설정을 올린 만큼 더 쓴다.

입력: 없음(시드 고정)
출력:
  QUESTIONS_DED : list[str]   문항 텍스트
  FAMILIES_DED  : list[str]   템플릿 id
  ANSWERS_DED   : list[str]   정답 글자. 전수 탐색이 구한 값이라 손으로 쓴 정답이 없다

설계 원칙:
  유일해만 채택한다. 답이 여러 개면 모델이 첫 번째 해를 찾자마자 끝내버려서
  '끝까지 검산하는' 비용이 사라진다. 그게 이 갈래를 쓰는 이유 자체다.

작성일: 2026-11-09
"""

from __future__ import annotations

import random
from itertools import combinations, permutations, product

from questions_v2 import make_mc, near_ints

SEED = 20261109
VARIANTS = 25

_NAMES = ["갑", "을", "병", "정", "무", "기"]
_DAYS = ["월", "화", "수", "목", "금"]

def _josa(w, with_b, without_b):
    """받침 유무로 조사를 고른다.

    이름이 갑·을·병·정(받침 있음)과 무(받침 없음)로 섞여 있는데 조사를 고정으로
    붙이면 "갑는", "을는", "병가" 같은 비문이 나온다(2026-11-12 발견). 문항을 사람이
    읽는 자리에 내놓을 때 바로 눈에 띄고, 모델에게도 불필요한 잡음이다.
    한글 음절은 (코드포인트 - 0xAC00) % 28 이 0 이 아니면 받침이 있다.
    """
    ch = w[-1]
    if not ("가" <= ch <= "힣"):
        return w + without_b
    return w + (with_b if (ord(ch) - 0xAC00) % 28 else without_b)


def _eun(w):
    """주격·주제 조사 은/는."""
    return _josa(w, "은", "는")


def _ga(w):
    """주격 조사 이/가."""
    return _josa(w, "이", "가")


def _eul(w):
    """목적격 조사 을/를."""
    return _josa(w, "을", "를")


def _wa(w):
    """접속·공동격 조사 와/과.

    은/는, 이/가와 받침 규칙이 반대다(받침 있으면 "과", 없으면 "와").
    고정으로 "와"를 붙여 "갑와", "을와" 같은 비문이 나왔다(2026-11-12).
    """
    return _josa(w, "과", "와")


# ──────────────────────────────────────────────────────────────────────────
# 1. 알리바이 — 진술 중 정해진 수만 참일 때 범인 찾기
# ──────────────────────────────────────────────────────────────────────────

def gen_alibi(rng, n):
    """n명 중 범인 1명. 각자 진술을 하고, 그중 정확히 m개만 참이다.

    범인 후보를 하나씩 놓고 진술의 참 개수를 세어 조건에 맞는 후보를 찾는다.
    후보가 정확히 하나인 경우만 문항으로 쓴다.
    """
    out, seen = [], set()
    for _ in range(n * 400):
        if len(out) >= n:
            break
        k = rng.randrange(4, 6)
        # claims[i] = (대상, 범인이라고 주장하는가)
        claims = []
        for i in range(k):
            j = rng.randrange(k)
            claims.append((j, rng.random() < 0.5))
        m = rng.randrange(1, k)          # 참인 진술의 개수
        hits = []
        for culprit in range(k):
            t = sum(1 for (j, says_guilty) in claims
                    if (j == culprit) == says_guilty)
            if t == m:
                hits.append(culprit)
        if len(hits) != 1:
            continue
        v = hits[0] + 1                  # 몇 번째 사람인지를 묻는다
        mc = make_mc(v, near_ints(v, rng, lo=1) + list(range(1, k + 1)), rng)
        if not mc:
            continue
        lines = []
        for i, (j, says_guilty) in enumerate(claims):
            tgt = "내가" if i == j else f"{_ga(_NAMES[j])}"
            what = "범인이다" if says_guilty else "범인이 아니다"
            if i == j and not says_guilty:
                tgt, what = "나는", "범인이 아니다"
            lines.append(f"{_NAMES[i]}: \"{tgt} {what}\"")
        stem = (f"{k}명 중 범인은 정확히 1명이다. " + " / ".join(lines)
                + f" 이 진술 중 정확히 {m}개만 참일 때, 범인은 앞에서 몇 번째 사람인가?")
        if stem in seen:
            continue
        seen.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 2. 진술 개수 — 숨은 수를 진술의 참 개수로 역추적
# ──────────────────────────────────────────────────────────────────────────

def _is_prime(x):
    if x < 2:
        return False
    i = 2
    while i * i <= x:
        if x % i == 0:
            return False
        i += 1
    return True


def _preds(rng, hi):
    """(설명, 판정함수) 후보 풀. 서로 독립적인 성질을 섞어야 유일해가 나온다."""
    d = rng.randrange(3, 8)
    t1 = rng.randrange(hi // 4, hi * 3 // 4)
    t2 = rng.randrange(hi // 4, hi * 3 // 4)
    sq = lambda x: int(x ** 0.5) ** 2 == x
    return [
        ("짝수이다", lambda x: x % 2 == 0),
        ("홀수이다", lambda x: x % 2 == 1),
        (f"{d}의 배수이다", lambda x, d=d: x % d == 0),
        (f"{t1}보다 크다", lambda x, t=t1: x > t),
        (f"{t2}보다 작다", lambda x, t=t2: x < t),
        ("소수이다", _is_prime),
        ("제곱수이다", sq),
        ("각 자리 숫자의 합이 짝수이다",
         lambda x: sum(int(c) for c in str(x)) % 2 == 0),
    ]


def gen_truth_count(rng, n):
    """1..hi 중 숨은 수 하나. 진술 k개 중 정확히 m개만 참이라는 조건으로 특정한다."""
    out, seen = [], set()
    for _ in range(n * 300):
        if len(out) >= n:
            break
        hi = rng.choice([30, 40, 50, 60])
        pool = _preds(rng, hi)
        k = rng.randrange(4, 6)
        chosen = rng.sample(pool, k)
        m = rng.randrange(1, k)
        hits = [x for x in range(1, hi + 1)
                if sum(1 for (_, f) in chosen if f(x)) == m]
        if len(hits) != 1:
            continue
        v = hits[0]
        mc = make_mc(v, near_ints(v, rng, lo=1), rng)
        if not mc:
            continue
        lines = " / ".join(f"({i + 1}) 그 수는 {t}" for i, (t, _) in enumerate(chosen))
        stem = (f"1부터 {hi}까지 중 어떤 수 하나를 두고 다음 진술을 했다. {lines} "
                f"이 중 정확히 {m}개만 참일 때 그 수는?")
        if stem in seen:
            continue
        seen.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 3. 목격자 교차검증 — 속성 진술 중 정해진 수만 맞음
# ──────────────────────────────────────────────────────────────────────────

_COLORS = ["빨강", "파랑", "초록", "검정"]
_KINDS = ["승용차", "승합차", "트럭", "오토바이"]
_PLACES = ["사거리", "주차장", "골목", "대로변"]


def gen_witness(rng, n):
    """용의 차량의 (색, 종류, 장소)를 목격자 진술로 특정한다.

    각 목격자는 속성 하나를 말하고, 진술 전체 중 정확히 m개만 맞다.
    모든 조합을 놓고 맞는 진술 수를 세어 후보가 하나인 경우만 쓴다.
    """
    out, seen = [], set()
    attrs = [("색", _COLORS), ("종류", _KINDS), ("장소", _PLACES)]
    for _ in range(n * 300):
        if len(out) >= n:
            break
        k = rng.randrange(4, 7)
        claims = []
        for _ in range(k):
            ai = rng.randrange(3)
            claims.append((ai, rng.randrange(len(attrs[ai][1]))))
        m = rng.randrange(1, k)
        hits = []
        for combo in product(range(4), repeat=3):
            t = sum(1 for (ai, vi) in claims if combo[ai] == vi)
            if t == m:
                hits.append(combo)
        if len(hits) != 1:
            continue
        combo = hits[0]
        ask = rng.randrange(3)
        name, vals = attrs[ask]
        correct = vals[combo[ask]]
        mc = make_mc(correct, [v for v in vals if v != correct], rng)
        if not mc:
            continue
        lines = []
        for i, (ai, vi) in enumerate(claims):
            lines.append(f"목격자{i + 1}: \"{_eun(attrs[ai][0])} {attrs[ai][1][vi]}이었다\"")
        stem = (f"용의 차량의 색·종류·장소를 두고 {k}명이 진술했다. "
                + " / ".join(lines)
                + f" 이 진술 중 정확히 {m}개만 맞을 때, {_eun(name)} 무엇인가?")
        if stem in seen:
            continue
        seen.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 4. 원탁 배치 — 이웃·맞은편 제약으로 자리 특정
# ──────────────────────────────────────────────────────────────────────────

def gen_seating(rng, n):
    """짝수 명이 원탁에 앉는다. 제약을 만족하는 배치가 유일한 경우만 쓴다.

    대칭을 둘 다 깨야 한다:
      * 회전 대칭 — 1번 사람의 자리를 0으로 고정해 없앤다. 안 하면 해가 항상 k개다.
      * 거울 대칭 — '이웃', '마주봄', '이웃 아님'은 모두 대칭 관계라 자리를 좌우로
        뒤집어도 그대로 성립한다. 1번을 고정해도 거울상이 또 하나의 해로 남아
        해의 수가 **항상 짝수**가 되고, 유일해가 원리적으로 나올 수 없다
        (2026-11-09 1차 생성에서 0개 나온 원인). 자기 자신이 거울상인 배치는
        서로 다른 두 사람이 한 자리에 앉아야 해서 존재하지 않는다.
        그래서 방향이 있는 제약('시계방향 바로 다음')을 최소 1개 넣는다.
    """
    out, seen = [], set()
    for _ in range(n * 400):
        if len(out) >= n:
            break
        k = rng.choice([4, 6])
        nxt, opp, notnb = [], [], []
        # 방향 제약 — 거울 대칭을 깨는 핵심. 반드시 1개 이상.
        for _ in range(rng.randrange(1, 3)):
            a, b = rng.sample(range(k), 2)
            nxt.append((a, b))
        if rng.random() < 0.7:
            a, b = rng.sample(range(k), 2)
            opp.append((a, b))
        if rng.random() < 0.6:
            a, b = rng.sample(range(k), 2)
            notnb.append((a, b))

        sols = []
        for p in permutations(range(1, k)):
            seats = (0,) + p          # seats[i] = i번 자리에 앉은 사람
            pos = {who: i for i, who in enumerate(seats)}
            ok = True
            for a, b in nxt:
                if (pos[a] + 1) % k != pos[b]:
                    ok = False
                    break
            if ok:
                for a, b in opp:
                    if (pos[a] - pos[b]) % k != k // 2:
                        ok = False
                        break
            if ok:
                for a, b in notnb:
                    if abs(pos[a] - pos[b]) % k in (1, k - 1):
                        ok = False
                        break
            if ok:
                sols.append(seats)
                if len(sols) > 1:
                    break
        if len(sols) != 1:
            continue
        who = rng.randrange(1, k)
        v = list(sols[0]).index(who) + 1
        mc = make_mc(v, list(range(1, k + 1)), rng)
        if not mc:
            continue
        parts = [f"{_NAMES[a]}의 시계방향 바로 다음 자리에 {_NAMES[b]}" for a, b in nxt]
        parts += [f"{_wa(_NAMES[a])} {_eun(_NAMES[b])} 마주봄" for a, b in opp]
        parts += [f"{_wa(_NAMES[a])} {_eun(_NAMES[b])} 이웃이 아님" for a, b in notnb]
        stem = (f"{k}명이 원탁에 둘러앉는다. 자리는 시계방향으로 1번부터 {k}번이고 "
                f"{_eun(_NAMES[0])} 1번 자리에 앉는다. " + ", ".join(parts)
                + f". {_eun(_NAMES[who])} 몇 번 자리인가?")
        if stem in seen:
            continue
        seen.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 5. 나이 추론 — 합·차·대소 제약으로 한 사람의 나이 특정
# ──────────────────────────────────────────────────────────────────────────

def gen_age(rng, n):
    """k명의 나이를 제약으로 특정한다. 후보 범위를 전수 탐색한다."""
    out, seen = [], set()
    for _ in range(n * 300):
        if len(out) >= n:
            break
        k = 3
        lo, hi = 10, 40
        true_ages = sorted(rng.sample(range(lo, hi + 1), k), reverse=True)
        a, b, c = true_ages
        facts = [
            (f"{_wa(_NAMES[0])} {_NAMES[1]}의 나이 합은 {a + b}", lambda x: x[0] + x[1] == a + b),
            (f"{_eun(_NAMES[1])} {_NAMES[2]}보다 {b - c}살 많다", lambda x: x[1] - x[2] == b - c),
            (f"세 사람의 나이 합은 {a + b + c}", lambda x: sum(x) == a + b + c),
            (f"{_eun(_NAMES[0])} {_NAMES[2]}의 나이의 {round((a / c), 2)}배",
             lambda x: abs(x[0] - x[2] * (a / c)) < 1e-9),
            (f"{_ga(_NAMES[0])} 가장 많고 {_ga(_NAMES[2])} 가장 적다",
             lambda x: x[0] > x[1] > x[2]),
        ]
        chosen = rng.sample(facts, 3)
        hits = []
        for cand in product(range(lo, hi + 1), repeat=k):
            if all(f(cand) for (_, f) in chosen):
                hits.append(cand)
                if len(hits) > 1:
                    break
        if len(hits) != 1:
            continue
        who = rng.randrange(k)
        v = hits[0][who]
        mc = make_mc(v, near_ints(v, rng, lo=lo), rng)
        if not mc:
            continue
        stem = (f"세 사람의 나이는 모두 {lo}살 이상 {hi}살 이하이다. "
                + ", ".join(t for (t, _) in chosen)
                + f". {_NAMES[who]}의 나이는?")
        if stem in seen:
            continue
        seen.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 6. 일정 배정 — 사람-요일 대응을 제약으로 특정
# ──────────────────────────────────────────────────────────────────────────

def gen_schedule(rng, n):
    """k명이 서로 다른 요일에 당번을 선다. 제약을 만족하는 배정이 유일한 경우만 쓴다."""
    out, seen = [], set()
    for _ in range(n * 300):
        if len(out) >= n:
            break
        k = rng.choice([4, 5])
        days = _DAYS[:k]
        nots, befores, adj = [], [], []
        for _ in range(rng.randrange(2, 4)):
            nots.append((rng.randrange(k), rng.randrange(k)))
        for _ in range(rng.randrange(1, 3)):
            a, b = rng.sample(range(k), 2)
            befores.append((a, b))
        if rng.random() < 0.5:
            a, b = rng.sample(range(k), 2)
            adj.append((a, b))

        sols = []
        for p in permutations(range(k)):      # p[i] = i번 사람의 요일 인덱스
            if any(p[who] == d for who, d in nots):
                continue
            if any(p[a] >= p[b] for a, b in befores):
                continue
            if any(p[b] - p[a] != 1 for a, b in adj):
                continue
            sols.append(p)
            if len(sols) > 1:
                break
        if len(sols) != 1:
            continue
        who = rng.randrange(k)
        correct = days[sols[0][who]]
        mc = make_mc(correct, [d for d in days if d != correct], rng)
        if not mc:
            continue
        parts = [f"{_eun(_NAMES[w])} {days[d]}요일이 아님" for w, d in nots]
        parts += [f"{_eun(_NAMES[a])} {_NAMES[b]}보다 앞 요일" for a, b in befores]
        parts += [f"{_NAMES[a]} 바로 다음 요일이 {_NAMES[b]}" for a, b in adj]
        stem = (f"{k}명이 {days[0]}요일부터 {days[-1]}요일까지 하루씩 당번을 선다. "
                + ", ".join(parts) + f". {_NAMES[who]}의 당번 요일은?")
        if stem in seen:
            continue
        seen.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 조립
# ──────────────────────────────────────────────────────────────────────────

FAMILY_SPECS_DED = [
    ("alibi", gen_alibi, VARIANTS),
    ("truth_count", gen_truth_count, VARIANTS),
    ("witness_attr", gen_witness, VARIANTS),
    ("seating_circle", gen_seating, VARIANTS),
    ("age_deduce", gen_age, VARIANTS),
    ("schedule_grid", gen_schedule, VARIANTS),
]


def _stem_of(q):
    return q.split(" A) ")[0]


def build():
    rng = random.Random(SEED + 1)
    qs, fams, ans = [], [], []
    seen = set()
    for fam, fn, want in FAMILY_SPECS_DED:
        got = fn(rng, want + 15)
        kept = 0
        for q, a in got:
            if kept >= want:
                break
            s = _stem_of(q)
            if s in seen:
                continue
            seen.add(s)
            qs.append(q)
            fams.append(fam)
            ans.append(a)
            kept += 1
    return qs, fams, ans


QUESTIONS_DED, FAMILIES_DED, ANSWERS_DED = build()


def self_test():
    from collections import Counter
    bad = 0
    print(f"총 {len(QUESTIONS_DED)}문항 / 템플릿 {len(set(FAMILIES_DED))}개")
    cnt = Counter(FAMILIES_DED)
    for fam, _, want in FAMILY_SPECS_DED:
        c = cnt.get(fam, 0)
        mark = "OK  " if c >= want else "부족"
        print(f"  {mark} {fam:16s} {c:3d}/{want}")
        if c == 0:
            bad += 1

    dup = len(QUESTIONS_DED) - len({_stem_of(q) for q in QUESTIONS_DED})
    print(f"중복 문항(본문): {dup}")
    if dup:
        bad += 1

    dist = Counter(ANSWERS_DED)
    print("정답 분포:", dict(sorted(dist.items())))
    if dist and max(dist.values()) > len(ANSWERS_DED) * 0.35:
        print("  경고: 정답 쏠림")

    for q in QUESTIONS_DED:
        if not all(f"{c})" in q for c in "ABCD"):
            print(f"  선택지 누락: {q[:60]}")
            bad += 1
            break

    print("\n자체 검사 " + ("통과" if bad == 0 else f"실패 {bad}건"))
    return bad


if __name__ == "__main__":
    import sys
    sys.exit(1 if self_test() else 0)
