"""문항 생성기 v2 — 솔버가 정답을 계산하는 파라메트릭 문항 세트.

목적:
  추론깊이 탐지 실험용 객관식 문항을 대량(목표 1000) 생성한다. 손으로 쓴 정답은
  1000개 규모에서 검증이 불가능하므로, 계산으로 풀리는 갈래는 **브루트포스 솔버가
  정답을 직접 구하고** 거기서 선택지를 만든다. 사람이 적는 정답이 없으니 오답이 없다.

입력: 없음(시드 고정 — 같은 코드면 같은 문항이 나온다)
출력:
  QUESTIONS_V2 : list[str]   문항 텍스트. questions_hard.QUESTIONS_HARD 와 같은 규격
  FAMILIES_V2  : list[str]   각 문항의 템플릿 id. 길이·순서가 QUESTIONS_V2 와 1:1
  ANSWERS_V2   : list[str]   정답 글자("A"~"D"). 불응·오답 판정용

왜 FAMILIES 가 필요한가:
  한 템플릿의 변형들(나이트 a1→h8, c3→f6, ...)은 서로 닮아 독립이 아니다. 신뢰구간을
  질문 단위로 재표집하면(e2_snr.boot_ci_cluster) 변형을 독립 표본으로 세어 구간이
  가짜로 좁아진다. 템플릿 단위로 묶어야 하므로 그 id 를 데이터에 같이 싣는다.

문항 설계 규칙 (2026-11-08 luna 선별 53문항 실측에서 도출):
  1. 유명 퍼즐의 교과서 파라미터를 피한다 — 하노이 원반 5개(답 31)는 설정 간 격차가
     30으로 최하위권이었다. 외워서 답하면 추론이 안 일어난다.
  2. 산술 갈래를 쓰지 않는다 — 0/7 통과. 절차가 정해진 계산은 한 번에 끝난다.
  3. 선택지 4개가 모두 그럴듯해야 한다. 자릿수·크기가 튀면 소거법으로 풀린다.
  4. 정답이 선택지 안에 반드시 하나만 있어야 한다(오답 중복 금지).
  5. 유일해가 아닌 문제는 버린다 — 답이 여러 개면 모델이 아무거나 고르고 끝낸다.

작성일: 2026-11-09
"""

from __future__ import annotations

import random
from functools import lru_cache
from itertools import permutations, product

# 시드 고정. 문항 세트는 재현 가능해야 한다(캡처를 나눠 받아도 같은 문항이어야 함).
SEED = 20261109

# 한 템플릿에서 뽑을 변형 수. 템플릿 수 x VARIANTS 가 이 모듈의 문항 수다.
VARIANTS = 25


# ──────────────────────────────────────────────────────────────────────────
# 공통 유틸
# ──────────────────────────────────────────────────────────────────────────

# 정답 위치를 A→B→C→D 로 돌려 쓰기 위한 카운터.
# 무작위 셔플에 맡기면 쏠린다(2026-11-09 1차 생성: B 79 / C 52, 기대값 62.5).
# 한 글자에 몰리면 모델이 내용을 안 보고 위치만으로 찍어 맞힐 수 있다.
_SLOT = [0]


def make_mc(correct, distractors, rng):
    """정답 하나와 오답 후보들로 4지선다 문자열과 정답 글자를 만든다.

    오답은 정답과 가까운 값이어야 한다. 값이 멀면 크기만 보고 찍을 수 있다.
    정답 위치는 호출될 때마다 A→B→C→D 로 순환한다(호출 순서가 고정이라 재현된다).
    반환: ("A) 4 B) 5 C) 6 D) 7", "C")
    """
    pool = []
    for d in distractors:
        if d != correct and d not in pool:
            pool.append(d)
    if len(pool) < 3:
        return None  # 그럴듯한 오답을 3개 못 만들면 그 변형은 버린다
    pos = _SLOT[0] % 4
    _SLOT[0] += 1
    wrong = pool[:3]
    rng.shuffle(wrong)
    opts = wrong[:pos] + [correct] + wrong[pos:]
    letter = "ABCD"[pos]
    text = " ".join(f"{c}) {v}" for c, v in zip("ABCD", opts))
    return text, letter


def near_ints(v, rng, lo=0):
    """정수 정답 주변의 그럴듯한 오답 후보. ±1~±3 범위에서 고른다."""
    cand = [v - 3, v - 2, v - 1, v + 1, v + 2, v + 3]
    cand = [c for c in cand if c >= lo and c != v]
    rng.shuffle(cand)
    return cand


def near_counts(v, rng):
    """개수형(값이 큰) 정답의 오답 후보. 비율로 흔들어 자릿수를 맞춘다."""
    cand = set()
    for f in (0.5, 0.75, 0.9, 1.1, 1.25, 1.5, 2.0):
        c = int(round(v * f))
        if c != v and c > 0:
            cand.add(c)
    for d in (-2, -1, 1, 2):
        if v + d > 0 and v + d != v:
            cand.add(v + d)
    out = sorted(cand)
    rng.shuffle(out)
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 1 — 나이트 최단 경로 (BFS)
# ──────────────────────────────────────────────────────────────────────────

_KNIGHT = [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]


def knight_dist(a, b):
    """8x8 체스판에서 a 칸부터 b 칸까지 나이트 최소 이동 수. a,b = (file, rank) 0-based."""
    if a == b:
        return 0
    seen = {a}
    frontier = [a]
    d = 0
    while frontier:
        d += 1
        nxt = []
        for (x, y) in frontier:
            for dx, dy in _KNIGHT:
                p = (x + dx, y + dy)
                if 0 <= p[0] < 8 and 0 <= p[1] < 8 and p not in seen:
                    if p == b:
                        return d
                    seen.add(p)
                    nxt.append(p)
        frontier = nxt
    return -1


def _sq(p):
    """(0,0) -> 'a1' 표기로."""
    return "abcdefgh"[p[0]] + str(p[1] + 1)


def gen_knight(rng, n):
    """나이트 최단 경로. 교과서 조합(a1-h8)을 피하고 거리 3 이상만 쓴다."""
    out = []
    tried = 0
    while len(out) < n and tried < n * 60:
        tried += 1
        a = (rng.randrange(8), rng.randrange(8))
        b = (rng.randrange(8), rng.randrange(8))
        if a == b or {_sq(a), _sq(b)} == {"a1", "h8"}:
            continue
        d = knight_dist(a, b)
        if d < 3:          # 1~2수는 암산으로 끝나 격차가 안 난다
            continue
        mc = make_mc(d, near_ints(d, rng, lo=1), rng)
        if not mc:
            continue
        q = f"체스판에서 나이트가 {_sq(a)}에서 {_sq(b)}까지 가는 최소 이동 수는? {mc[0]}"
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 2 — 물통 (상태공간 BFS)
# ──────────────────────────────────────────────────────────────────────────

def jug_min_ops(cap_a, cap_b, target):
    """두 물통으로 target 리터를 만드는 최소 조작 횟수. 불가능하면 -1.

    조작 6가지: 각각 채우기/비우기, 서로 붓기. 붓기는 받는 쪽이 차거나 주는 쪽이 빌 때까지.
    """
    start = (0, 0)
    seen = {start}
    frontier = [start]
    steps = 0
    if target == 0:
        return 0
    while frontier:
        steps += 1
        nxt = []
        for (a, b) in frontier:
            moves = [
                (cap_a, b), (a, cap_b), (0, b), (a, 0),
                (a - min(a, cap_b - b), b + min(a, cap_b - b)),
                (a + min(b, cap_a - a), b - min(b, cap_a - a)),
            ]
            for m in moves:
                if m in seen:
                    continue
                if target in m:
                    return steps
                seen.add(m)
                nxt.append(m)
        frontier = nxt
    return -1


def gen_jug(rng, n):
    """물통 문제. 5/3 리터 교과서 조합을 피한다."""
    out = []
    tried = 0
    while len(out) < n and tried < n * 80:
        tried += 1
        ca = rng.randrange(7, 18)
        cb = rng.randrange(3, ca)
        if (ca, cb) == (5, 3) or (ca, cb) == (8, 5):
            continue
        t = rng.randrange(1, cb + 1)
        d = jug_min_ops(ca, cb, t)
        if d < 4 or d > 12:      # 너무 쉬우면 격차가 없고, 너무 길면 토큰 상한을 친다
            continue
        mc = make_mc(d, near_ints(d, rng, lo=1), rng)
        if not mc:
            continue
        q = (f"{ca}리터와 {cb}리터 물통만으로 정확히 {t}리터를 만드는 "
             f"최소 조작 횟수는? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 3 — 강 건너기 (선교사·식인종 일반화, BFS)
# ──────────────────────────────────────────────────────────────────────────

def river_min_cross(n_mis, n_can, boat):
    """선교사 n_mis명·식인종 n_can명을 boat 인승 배로 건네는 최소 도강 횟수. 불가능 -1.

    인원 수를 다르게 둘 수 있게 일반화했다. 쌍으로 묶으면 (쌍 수) x (배 크기) 조합이
    열 몇 개뿐이라 변형을 25개 못 만든다.

    상태 = (출발쪽 선교사, 출발쪽 식인종, 배가 출발쪽인가).
    제약: 어느 쪽이든 선교사가 0명이 아니면 식인종 수가 선교사 수를 넘으면 안 된다.
    """
    def ok(m, c):
        if m < 0 or c < 0 or m > n_mis or c > n_can:
            return False
        if m > 0 and c > m:
            return False
        rm, rc = n_mis - m, n_can - c
        if rm > 0 and rc > rm:
            return False
        return True

    start = (n_mis, n_can, True)
    goal = (0, 0, False)
    if not ok(n_mis, n_can):
        return -1
    seen = {start}
    frontier = [start]
    steps = 0
    while frontier:
        steps += 1
        nxt = []
        for (m, c, side) in frontier:
            for i, j in product(range(boat + 1), repeat=2):
                if not (1 <= i + j <= boat):
                    continue
                # 배에 탄 인원도 안전해야 한다
                if i > 0 and j > i:
                    continue
                if side:
                    s = (m - i, c - j, False)
                else:
                    s = (m + i, c + j, True)
                if not ok(s[0], s[1]) or s in seen:
                    continue
                if s == goal:
                    return steps
                seen.add(s)
                nxt.append(s)
        frontier = nxt
    return -1


def gen_river(rng, n):
    """강 건너기. 3쌍·2인승(교과서, 답 11)을 피하고 인원 수를 비대칭으로도 둔다."""
    out = []
    combos = []
    for m in range(3, 9):
        for c in range(2, m + 1):
            for bt in (2, 3, 4):
                if (m, c, bt) == (3, 3, 2):     # 교과서 값 11 제외
                    continue
                combos.append((m, c, bt))
    rng.shuffle(combos)
    for m, c, bt in combos:
        if len(out) >= n:
            break
        d = river_min_cross(m, c, bt)
        if d < 5:            # 3회 안쪽이면 암산으로 끝난다
            continue
        mc = make_mc(d, near_ints(d, rng, lo=1), rng)
        if not mc:
            continue
        q = (f"선교사 {m}명과 식인종 {c}명이 {bt}인승 배로 강을 건넌다. "
             f"배에서든 양쪽 기슭에서든 선교사가 한 명이라도 있는 곳에서는 "
             f"식인종이 선교사보다 많으면 안 된다. 최소 도강 횟수는? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 4 — 장애물 격자 경로 수 (DP)
# ──────────────────────────────────────────────────────────────────────────

def lattice_paths(w, h, blocked):
    """(0,0)에서 (w,h)까지 오른쪽·위로만 가는 경로 수. blocked = 막힌 교차점 집합."""
    grid = [[0] * (h + 1) for _ in range(w + 1)]
    for x in range(w + 1):
        for y in range(h + 1):
            if (x, y) in blocked:
                grid[x][y] = 0
                continue
            if x == 0 and y == 0:
                grid[x][y] = 1
                continue
            v = 0
            if x > 0:
                v += grid[x - 1][y]
            if y > 0:
                v += grid[x][y - 1]
            grid[x][y] = v
    return grid[w][h]


def gen_lattice(rng, n):
    """장애물 있는 격자 경로 수. 장애물이 없으면 이항계수라 공식으로 끝나므로 반드시 막는다."""
    out = []
    for _ in range(n * 40):
        if len(out) >= n:
            break
        w = rng.randrange(3, 7)
        h = rng.randrange(3, 7)
        k = rng.randrange(1, 4)
        blocked = set()
        while len(blocked) < k:
            p = (rng.randrange(1, w), rng.randrange(1, h))
            blocked.add(p)
        v = lattice_paths(w, h, blocked)
        if v < 4:
            continue
        mc = make_mc(v, near_counts(v, rng), rng)
        if not mc:
            continue
        bl = ", ".join(f"({x},{y})" for x, y in sorted(blocked))
        q = (f"{w}x{h} 격자에서 (0,0)부터 ({w},{h})까지 오른쪽·위로만 이동한다. "
             f"교차점 {_num_eun(bl)} 공사로 지날 수 없을 때 경로의 수는? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 5 — N퀸 배치 수 (백트래킹)
# ──────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def queens_count(n, forbid_row=None):
    """n x n 판에 퀸 n개를 서로 공격받지 않게 놓는 배치 수.

    forbid_row 가 주어지면 '첫 열의 퀸이 그 행이 아닌' 배치만 센다(변형 생성용).
    """
    sols = 0
    cols = [0] * n

    def place(r, c_mask, d1, d2):
        nonlocal sols
        if r == n:
            sols += 1
            return
        for c in range(n):
            if c_mask >> c & 1:
                continue
            if d1 >> (r + c) & 1:
                continue
            if d2 >> (r - c + n) & 1:
                continue
            if r == 0 and forbid_row is not None and c == forbid_row:
                continue
            place(r + 1, c_mask | 1 << c, d1 | 1 << (r + c), d2 | 1 << (r - c + n))

    place(0, 0, 0, 0)
    return sols


def gen_queens(rng, n):
    """N퀸. 8x8(답 92)은 유명하므로 판 크기를 흔들고 '첫 행 제약' 변형을 섞는다."""
    out = []
    combos = []
    for size in (5, 6, 7, 8, 9):
        combos.append((size, None))
        for fr in range(size):
            combos.append((size, fr))
    rng.shuffle(combos)
    for size, fr in combos:
        if len(out) >= n:
            break
        if (size, fr) == (8, None):     # 교과서 값 92 제외
            continue
        v = queens_count(size, fr)
        if v < 2:
            continue
        mc = make_mc(v, near_counts(v, rng), rng)
        if not mc:
            continue
        if fr is None:
            q = (f"{size}x{size} 체스판에 퀸 {size}개를 서로 공격받지 않게 놓는 "
                 f"서로 다른 배치의 수는? {mc[0]}")
        else:
            q = (f"{size}x{size} 체스판에 퀸 {size}개를 서로 공격받지 않게 놓되 "
                 f"첫 번째 행의 퀸은 {fr + 1}번째 열에 올 수 없다. 배치의 수는? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 6 — 거짓말쟁이 (진리표 전수 탐색)
# ──────────────────────────────────────────────────────────────────────────

_NAMES = ["갑", "을", "병", "정", "무", "기", "경"]


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


# 숫자를 한국어로 읽었을 때 끝소리에 받침이 있는지. 0 영, 1 일, 3 삼, 6 육,
# 7 칠, 8 팔 은 받침이 있고 2 이, 4 사, 5 오, 9 구 는 없다. 끝자리 0 은
# 십·백·천·만 으로 읽히므로 모두 받침이 있다.
_DIGIT_BATCHIM = {"0": True, "1": True, "2": False, "3": True, "4": False,
                  "5": False, "6": True, "7": True, "8": True, "9": False}


def _num_ga(n):
    """숫자 뒤 주격 조사 이/가.

    "{target}이" 처럼 고정으로 붙이면 target=12 일 때 "12이"(십이이)가 된다.
    끝자리 숫자의 읽는 소리로 고른다. 괄호가 섞인 좌표 문자열도 받으므로
    마지막 숫자 문자를 찾아 쓴다.
    """
    t = str(n)
    for ch in reversed(t):
        if ch.isdigit():
            return t + ("이" if _DIGIT_BATCHIM[ch] else "가")
    return t + "가"


def _num_eun(n):
    """숫자 뒤 주제 조사 은/는. 규칙은 _num_ga 와 같다."""
    t = str(n)
    for ch in reversed(t):
        if ch.isdigit():
            return t + ("은" if _DIGIT_BATCHIM[ch] else "는")
    return t + "는"

def liar_solve(n, claims):
    """가능한 정직/거짓 배치를 전부 반환한다. True = 정직.

    claims 두 종류:
      ("accuse", i, j, pol) — i 가 "j는 정직하다(pol=True)/거짓말쟁이다(pol=False)"
      ("count",  i, m)      — i 가 "우리 중 정직한 사람은 정확히 m명이다"

    왜 count 가 필요한가:
      accuse 진술만 쓰면 각 진술이 assign[i] XOR assign[j] = 상수 꼴이라 전체가
      GF(2) 선형계가 된다. 그 해집합은 아핀 부분공간이므로 크기가 0 또는 2^d 이고
      **정확히 1개가 될 수 없다.** 실제로 유일해 조건을 걸었더니 한 문항도 생성되지
      않았다(2026-11-09). 개수 진술은 선형이 아니라 유일해를 만들어 준다.
    """
    sols = []
    for assign in product([True, False], repeat=n):
        ok = True
        for cl in claims:
            if cl[0] == "accuse":
                _, i, j, pol = cl
                stmt_true = (assign[j] == pol)
            else:
                _, i, m = cl
                stmt_true = (sum(assign) == m)
            if assign[i] != stmt_true:
                ok = False
                break
        if ok:
            sols.append(assign)
    return sols


def gen_liar(rng, n):
    """거짓말쟁이 퍼즐. 개수 진술을 최소 1개 섞어 유일해를 만든다."""
    out = []
    seen_q = set()
    for _ in range(n * 400):
        if len(out) >= n:
            break
        k = rng.randrange(4, 8)
        n_count = rng.randrange(1, 3)              # 개수 진술 1~2개는 반드시 넣는다
        counters = rng.sample(range(k), n_count)
        claims = []
        for i in range(k):
            if i in counters:
                claims.append(("count", i, rng.randrange(0, k + 1)))
            else:
                j = rng.randrange(k)
                while j == i:
                    j = rng.randrange(k)
                claims.append(("accuse", i, j, rng.random() < 0.5))
        sols = liar_solve(k, claims)
        if len(sols) != 1:          # 유일해가 아니면 버린다
            continue
        v = sum(sols[0])
        mc = make_mc(v, near_ints(v, rng, lo=0), rng)
        if not mc:
            continue
        lines = []
        for cl in claims:
            if cl[0] == "accuse":
                _, i, j, pol = cl
                what = "정직하다" if pol else "거짓말쟁이다"
                lines.append(f"{_NAMES[i]}: \"{_eun(_NAMES[j])} {what}\"")
            else:
                _, i, m = cl
                lines.append(f"{_NAMES[i]}: \"우리 중 정직한 사람은 정확히 {m}명이다\"")
        stem = ("정직한 사람은 참만 말하고 거짓말쟁이는 거짓만 말한다. "
                + " / ".join(lines)
                + " 정직한 사람은 몇 명인가?")
        if stem in seen_q:
            continue
        seen_q.add(stem)
        out.append((f"{stem} {mc[0]}", mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 7 — 줄 세우기 제약 (순열 전수 탐색)
# ──────────────────────────────────────────────────────────────────────────

def order_solve(n, befores, adjacents, fixed):
    """제약을 만족하는 순열을 전부 찾는다.

    befores   = [(a, b)]  a가 b보다 앞
    adjacents = [(a, b)]  a 바로 뒤에 b
    fixed     = [(a, pos)] a가 정확히 pos 번째(0-based)
    """
    sols = []
    for p in permutations(range(n)):
        pos = {v: i for i, v in enumerate(p)}
        if any(pos[a] > pos[b] for a, b in befores):
            continue
        if any(pos[b] - pos[a] != 1 for a, b in adjacents):
            continue
        if any(pos[a] != k for a, k in fixed):
            continue
        sols.append(p)
    return sols


def gen_order(rng, n):
    """줄 세우기. 유일해만 남기고 특정 인물의 순번을 묻는다."""
    out = []
    for _ in range(n * 150):
        if len(out) >= n:
            break
        k = rng.randrange(5, 7)
        befores, adjacents, fixed = [], [], []
        for _ in range(rng.randrange(2, 4)):
            a, b = rng.sample(range(k), 2)
            befores.append((a, b))
        if rng.random() < 0.6:
            a, b = rng.sample(range(k), 2)
            adjacents.append((a, b))
        if rng.random() < 0.5:
            fixed.append((rng.randrange(k), rng.randrange(k)))
        sols = order_solve(k, befores, adjacents, fixed)
        if len(sols) != 1:
            continue
        who = rng.randrange(k)
        v = sols[0].index(who) + 1
        mc = make_mc(v, near_ints(v, rng, lo=1), rng)
        if not mc:
            continue
        parts = [f"{_eun(_NAMES[a])} {_NAMES[b]}보다 앞" for a, b in befores]
        parts += [f"{_NAMES[a]} 바로 뒤에 {_NAMES[b]}" for a, b in adjacents]
        parts += [f"{_eun(_NAMES[a])} 정확히 {p + 1}번째" for a, p in fixed]
        q = (f"{k}명이 한 줄로 선다. " + ", ".join(parts)
             + f". {_eun(_NAMES[who])} 앞에서 몇 번째인가? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 8 — 도미노 덮기 (막힌 칸 포함, 재귀 전수 탐색)
# ──────────────────────────────────────────────────────────────────────────

def tiling_count(w, h, blocked):
    """w x h 보드에서 막힌 칸을 뺀 나머지를 1x2 도미노로 덮는 방법의 수."""
    cells = [(x, y) for y in range(h) for x in range(w) if (x, y) not in blocked]
    cellset = set(cells)
    order = sorted(cellset, key=lambda p: (p[1], p[0]))

    def rec(used):
        nxt = None
        for p in order:
            if p not in used:
                nxt = p
                break
        if nxt is None:
            return 1
        total = 0
        x, y = nxt
        for d in ((1, 0), (0, 1)):
            q = (x + d[0], y + d[1])
            if q in cellset and q not in used:
                total += rec(used | {nxt, q})
        return total

    if len(cells) % 2:
        return 0
    return rec(frozenset())


def gen_tiling(rng, n):
    """도미노 덮기. 2xN(피보나치)은 유명하므로 폭 3 이상 + 막힌 칸을 쓴다."""
    out = []
    for _ in range(n * 60):
        if len(out) >= n:
            break
        w = rng.randrange(3, 6)
        h = rng.randrange(3, 6)
        k = 2 if (w * h) % 2 == 0 else 1
        blocked = set()
        while len(blocked) < k:
            blocked.add((rng.randrange(w), rng.randrange(h)))
        if (w * h - len(blocked)) % 2:
            continue
        v = tiling_count(w, h, blocked)
        if v < 3 or v > 20000:
            continue
        mc = make_mc(v, near_counts(v, rng), rng)
        if not mc:
            continue
        bl = ", ".join(f"({x + 1},{y + 1})" for x, y in sorted(blocked))
        q = (f"{w}x{h} 보드에서 칸 {_num_ga(bl)} 막혀 있다. 나머지를 1x2 도미노로 "
             f"빈틈없이 덮는 방법의 수는? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 9 — 부분집합 합 (전수 탐색)
# ──────────────────────────────────────────────────────────────────────────

def subset_count(nums, target):
    """nums 의 부분집합 중 합이 target 인 것의 수(공집합 포함 안 함)."""
    cnt = 0
    k = len(nums)
    for mask in range(1, 1 << k):
        s = sum(nums[i] for i in range(k) if mask >> i & 1)
        if s == target:
            cnt += 1
    return cnt


def gen_subset(rng, n):
    """부분집합 합. 공식이 없어 실제로 세어봐야 한다."""
    out = []
    for _ in range(n * 60):
        if len(out) >= n:
            break
        k = rng.randrange(6, 9)
        nums = sorted(rng.sample(range(2, 30), k))
        target = rng.randrange(sum(nums) // 4, sum(nums) // 2)
        v = subset_count(nums, target)
        if v < 2 or v > 40:
            continue
        mc = make_mc(v, near_ints(v, rng, lo=0), rng)
        if not mc:
            continue
        q = (f"수 {{{', '.join(map(str, nums))}}} 중 몇 개를 골라 합이 정확히 "
             f"{_num_ga(target)} 되게 하는 방법의 수는? (고르는 순서는 구분하지 않는다) {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 솔버 10 — 하노이 변형 (인접 기둥만 이동, BFS)
# ──────────────────────────────────────────────────────────────────────────

def hanoi_adjacent(n, src=0, dst=2):
    """기둥 3개가 일렬이고 양끝끼리는 직접 못 옮길 때, 원반 n개 이동 최소 횟수.

    표준 하노이(2^n-1)는 유명해서 암기로 답한다. 인접 제약을 걸면 양 끝 사이는
    3^n-1 인데 이 값도 공식이 알려져 있으므로 BFS 로 직접 구해 공식 의존을 피한다.
    src/dst 를 바꾸면 공식이 안 통하는 변형이 나온다(끝→가운데 등).
    """
    start = tuple([src] * n)        # 각 원반이 올라간 기둥 번호
    goal = tuple([dst] * n)
    seen = {start}
    frontier = [start]
    steps = 0
    while frontier:
        steps += 1
        nxt = []
        for st in frontier:
            tops = {}
            for disk in range(n):   # disk 0 이 가장 작다
                p = st[disk]
                if p not in tops:
                    tops[p] = disk
            for src, disk in tops.items():
                for dst in (src - 1, src + 1):
                    if not 0 <= dst <= 2:
                        continue
                    if dst in tops and tops[dst] < disk:
                        continue
                    ns = list(st)
                    ns[disk] = dst
                    ns = tuple(ns)
                    if ns in seen:
                        continue
                    if ns == goal:
                        return steps
                    seen.add(ns)
                    nxt.append(ns)
        frontier = nxt
    return -1


_PEG = {0: "왼쪽 끝", 1: "가운데", 2: "오른쪽 끝"}


def gen_hanoi(rng, n):
    """하노이 인접 제약 변형. 원반 수 + 출발/도착 기둥을 함께 흔든다.

    원반 수만 바꾸면 같은 문장이 반복돼 선택지만 다른 사실상 중복이 된다.
    출발·도착을 바꾸면 끝→가운데처럼 공식이 안 알려진 경우가 나온다.
    """
    out = []
    combos = [(d, s, t) for d in (3, 4, 5, 6, 7)
              for s in (0, 1, 2) for t in (0, 1, 2) if s != t]
    rng.shuffle(combos)
    for disks, src, dst in combos:
        if len(out) >= n:
            break
        v = hanoi_adjacent(disks, src, dst)
        if v < 4:
            continue
        mc = make_mc(v, near_counts(v, rng), rng)
        if not mc:
            continue
        q = (f"기둥 3개가 일렬로 놓여 있고 양 끝 기둥끼리는 원반을 직접 옮길 수 없다"
             f"(가운데를 반드시 거쳐야 한다). 원반 {disks}개를 "
             f"{_PEG[src]} 기둥에서 {_PEG[dst]} 기둥으로 모두 옮기는 "
             f"최소 이동 횟수는? {mc[0]}")
        out.append((q, mc[1]))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 조립
# ──────────────────────────────────────────────────────────────────────────

# (템플릿 id, 생성 함수, 뽑을 변형 수)
FAMILY_SPECS = [
    ("knight_path", gen_knight, VARIANTS),
    ("jug", gen_jug, VARIANTS),
    ("river_cross", gen_river, VARIANTS),
    ("lattice_block", gen_lattice, VARIANTS),
    ("queens_count", gen_queens, VARIANTS),
    ("liar", gen_liar, VARIANTS),
    ("order_line", gen_order, VARIANTS),
    ("domino_tiling", gen_tiling, VARIANTS),
    ("subset_sum", gen_subset, VARIANTS),
    ("hanoi_adjacent", gen_hanoi, VARIANTS),
]


def _stem(q):
    """선택지를 뗀 문제 본문. make_mc 가 만든 선택지는 항상 ' A) ' 로 시작한다.

    본문이 같고 선택지만 다른 문항은 같은 문제를 두 번 내는 것이라 다양성이 0이다.
    전체 문자열이 아니라 본문 기준으로 걸러야 이런 유사 중복까지 잡힌다.
    """
    return q.split(" A) ")[0]


def build():
    """모든 템플릿을 돌려 (문항, 템플릿id, 정답) 세 리스트를 만든다.

    생성기에 목표보다 넉넉히 요청한 뒤 본문 기준 중복을 걷어내고 앞에서 want 개만
    취한다. 같은 파라미터가 두 번 뽑히면 문항이 통째로 겹치기 때문이다.
    """
    rng = random.Random(SEED)
    qs, fams, ans = [], [], []
    seen = set()
    for fam, fn, want in FAMILY_SPECS:
        got = fn(rng, want + 15)
        kept = 0
        for q, a in got:
            if kept >= want:
                break
            s = _stem(q)
            if s in seen:
                continue
            seen.add(s)
            qs.append(q)
            fams.append(fam)
            ans.append(a)
            kept += 1
    return qs, fams, ans


QUESTIONS_V2, FAMILIES_V2, ANSWERS_V2 = build()


# ──────────────────────────────────────────────────────────────────────────
# 자체 검사 — 솔버가 알려진 값을 맞히는지 확인한다.
# 여기서 틀리면 생성된 문항의 정답이 전부 틀린 것이므로 반드시 통과해야 한다.
# ──────────────────────────────────────────────────────────────────────────

def self_test():
    checks = [
        ("나이트 a1->h8 = 6", knight_dist((0, 0), (7, 7)), 6),
        ("나이트 a1->b2 = 4", knight_dist((0, 0), (1, 1)), 4),
        ("물통 5,3 -> 4 = 6", jug_min_ops(5, 3, 4), 6),
        ("강건너기 3쌍 2인승 = 11", river_min_cross(3, 3, 2), 11),
        ("강건너기 3쌍 3인승 = 5", river_min_cross(3, 3, 3), 5),
        ("격자 4x4 장애물없음 = 70", lattice_paths(4, 4, set()), 70),
        ("8퀸 = 92", queens_count(8, None), 92),
        ("6퀸 = 4", queens_count(6, None), 4),
        ("2x4 도미노 = 5", tiling_count(2, 4, set()), 5),
        ("4x4 도미노 = 36", tiling_count(4, 4, set()), 36),
        ("하노이 인접 3개 끝->끝 = 26", hanoi_adjacent(3, 0, 2), 26),
        ("하노이 인접 4개 끝->끝 = 80", hanoi_adjacent(4, 0, 2), 80),
        # 끝->가운데는 공식이 따로 없다. BFS 가 제대로 도는지 보는 값.
        ("하노이 인접 1개 끝->가운데 = 1", hanoi_adjacent(1, 0, 1), 1),
        ("하노이 인접 2개 끝->끝 = 8", hanoi_adjacent(2, 0, 2), 8),
    ]
    # 템플릿별 생성 수가 목표에 못 미치면 경고한다(2026-11-09: liar 가 0개 나왔던 건).
    from collections import Counter as _C
    short = [(f, c) for f, c in _C(FAMILIES_V2).items() if c < VARIANTS]
    missing = [f for f, _, _ in FAMILY_SPECS if f not in set(FAMILIES_V2)]
    bad = 0
    for name, got, want in checks:
        ok = got == want
        print(f"  {'OK  ' if ok else 'FAIL'} {name}  (계산값 {got})")
        if not ok:
            bad += 1

    # 생성 결과 요약
    print(f"\n총 {len(QUESTIONS_V2)}문항 / 템플릿 {len(set(FAMILIES_V2))}개")
    from collections import Counter
    for fam, c in Counter(FAMILIES_V2).most_common():
        print(f"  {fam:16s} {c:3d}")

    # 정답 쏠림 검사 — 특정 글자에 몰리면 모델이 찍어서 맞힐 수 있다
    dist = Counter(ANSWERS_V2)
    print("\n정답 분포:", dict(sorted(dist.items())))
    if dist and max(dist.values()) > len(ANSWERS_V2) * 0.35:
        print("  경고: 정답이 한 글자에 쏠렸다. 셔플 확인 필요")

    # 중복 문항 검사 — 본문 기준(선택지만 다른 유사 중복까지 잡는다)
    dup = len(QUESTIONS_V2) - len(set(QUESTIONS_V2))
    dup_stem = len(QUESTIONS_V2) - len({_stem(q) for q in QUESTIONS_V2})
    print(f"중복 문항: 전체일치 {dup} / 본문일치 {dup_stem}")
    if dup or dup_stem:
        bad += 1

    # 템플릿 생성 부족 — 솔버는 맞아도 변형을 못 뽑으면 설계가 틀린 것이다
    if missing:
        print(f"  실패: 한 문항도 못 만든 템플릿 {missing}")
        bad += 1
    if short:
        print("  경고: 목표 미달 템플릿 " +
              ", ".join(f"{f}({c}/{VARIANTS})" for f, c in sorted(short)))

    print("\n자체 검사 " + ("통과" if bad == 0 else f"실패 {bad}건"))
    return bad


if __name__ == "__main__":
    import sys
    sys.exit(1 if self_test() else 0)
