"""
questions_nil.py — '추론할 여지가 물리적으로 없는' 극단 대조 문항 세트.

목적
----
`questions_trivial.py` 대조군에서 한 가지가 안 갈렸다.
trivial(암산 한 번·상식 한 개)에서 terra/sol/astra 는 낮은 설정에서 추론 토큰이
**정확히 0** 인데(12/12), luna 만 16~24 토큰을 깔고 0 으로 내려가지 않는다(60콜 중 0 은 1건).
여기서 두 해석이 경쟁한다.

  (가) 문턱형 — luna 에게도 '생각할지 말지' 게이트가 있는데, 능력이 낮아서 문턱이 낮다.
                "3 + 4" 조차 문턱을 넘어버린 것뿐이다.
  (나) 바닥형 — luna 에는 게이트가 없거나 꺼지지 않는다. 무조건 짧은 스크래치패드를 쓴다.

trivial 로는 못 가른다. 암산도 한 걸음은 한 걸음이기 때문이다.
그래서 **한 걸음조차 없는** 문항이 필요하다. 정답이 문제 안에 글자 그대로 적혀 있어
베껴 쓰기만 하면 끝나는 문항이다. 여기서도 luna 가 토큰을 쓰면 (나), 0 으로 내려가면 (가).

왜 이 구분이 중요한가
---------------------
Task A 의 천장을 설명하는 모형이 달라진다.
(가)면 '난도 문턱이 능력에 따라 다르다'는 한 축으로 전부 설명되고,
(나)면 모델마다 구조적 바닥이 따로 있다는 두 번째 상수를 모형에 넣어야 한다.
→ `_notes/암호화 트래픽 Reasoning Effort 탐지 — 연구설계.md` 의
   "경량 모델이 더 추론한다" 및 "세대 가설 기각" 항목과 이어진다.

설계 원칙
---------
- **정답이 지문에 글자 그대로 있다.** 계산·회상·비교가 전부 없다. 전사(transcription)만 남긴다.
- 정답 글자를 A/B/C/D 에 **정확히 3개씩** 둔다. trivial 세트는 A2/B4/C5/D1 로 치우쳐 있어
  "C 만 찍어도 42%" 라는 베이스라인 문제가 있었다. 여기서는 전부 찍어도 25% 다.
- 지시 문형을 세 갈래로 나눈다(echo/given/repeat). 한 문형만 쓰면 그 문형 특유의
  처리 경로를 본 것인지 난도를 본 것인지 구분이 안 된다.

입력: 없음(상수 모듈).
출력: QUESTIONS_NIL / FAMILIES_NIL / ANSWERS_NIL — screen_qset.py 가 INSTR 을 붙여 쓴다.

작성일: 2026-11-24
"""

# 문항·템플릿 id·정답을 한 자리에서 관리한다. 따로 두면 순서가 어긋나도 조용히 통과한다.
_ITEMS = [
    # echo — 출력할 글자를 지시문이 직접 지정한다.
    ("echo_a",   "A 를 그대로 출력하라. A) A B) B C) C D) D", "A"),
    ("echo_b",   "B 를 그대로 출력하라. A) A B) B C) C D) D", "B"),
    ("echo_c",   "C 를 그대로 출력하라. A) A B) B C) C D) D", "C"),
    ("echo_d",   "D 를 그대로 출력하라. A) A B) B C) C D) D", "D"),
    # given — 정답을 먼저 알려주고 그것을 묻는다.
    ("given_a",  "정답은 A 다. 정답은 무엇인가? A) A B) B C) C D) D", "A"),
    ("given_b",  "정답은 B 다. 정답은 무엇인가? A) A B) B C) C D) D", "B"),
    ("given_c",  "정답은 C 다. 정답은 무엇인가? A) A B) B C) C D) D", "C"),
    ("given_d",  "정답은 D 다. 정답은 무엇인가? A) A B) B C) C D) D", "D"),
    # repeat — 제시된 글자를 따라 쓰게 한다.
    ("repeat_a", "아래 글자를 따라 쓰라: A. A) A B) B C) C D) D", "A"),
    ("repeat_b", "아래 글자를 따라 쓰라: B. A) A B) B C) C D) D", "B"),
    ("repeat_c", "아래 글자를 따라 쓰라: C. A) A B) B C) C D) D", "C"),
    ("repeat_d", "아래 글자를 따라 쓰라: D. A) A B) B C) C D) D", "D"),
]

QUESTIONS_NIL = [q for _, q, _ in _ITEMS]
FAMILIES_NIL = [f for f, _, _ in _ITEMS]
ANSWERS_NIL = [a for _, _, a in _ITEMS]

assert len(ANSWERS_NIL) == len(QUESTIONS_NIL) == len(FAMILIES_NIL), "문항·정답·템플릿 수가 어긋난다"
assert sorted(ANSWERS_NIL).count("A") == 3, "정답 분포가 3/3/3/3 이 아니다"
assert len(set(ANSWERS_NIL)) == 4, "정답 글자가 네 종류가 아니다"
