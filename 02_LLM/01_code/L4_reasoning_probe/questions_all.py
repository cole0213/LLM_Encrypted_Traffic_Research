"""v2 문항 세트 통합 — 세 모듈을 하나로 합치고 템플릿 id 를 같이 싣는다.

목적:
  questions_v2(솔버 탐색) · questions_v2_open(정답 없음) · questions_v2_deduce(증거 추론)
  를 한 리스트로 합친다. 선별기와 캡처 러너는 `--qset v2` 로 이걸 쓴다.

왜 통합 모듈이 따로 필요한가:
  기존 러너들은 QUESTIONS 를 '문자열 리스트'로만 받고 q_idx 는 그 리스트의 위치다.
  v2 는 문항마다 템플릿 id 가 붙어야 하는데(아래 참조) 리스트 규격을 깨면 기존
  스크립트가 전부 멈춘다. 그래서 문항 리스트는 그대로 두고, 같은 길이·같은 순서의
  FAMILIES 리스트를 옆에 둔다. 쓰는 쪽에서 q_idx 로 바로 당겨 쓸 수 있다.

왜 템플릿 id 가 필요한가:
  파라메트릭 갈래는 한 템플릿에서 25개 변형이 나온다(나이트 a1→h8, c3→f6, ...).
  이들은 서로 닮아 독립 표본이 아니다. 신뢰구간을 질문 단위로 재표집할 때
  (e2_snr.boot_ci_cluster) 변형을 각각 독립으로 세면 표본이 실제보다 많은 정보를
  가진 것처럼 취급돼 구간이 가짜로 좁아진다. 템플릿 단위로 묶어야 한다.
  반면 페르미·딜레마는 문항 하나하나가 다른 문제라 각자가 독립 클러스터다.

입력: 없음
출력:
  QUESTIONS_V2_ALL : list[str]        문항 텍스트(기존 QUESTIONS 와 같은 규격)
  FAMILIES_V2_ALL  : list[str]        템플릿 id. QUESTIONS_V2_ALL 과 길이·순서 1:1
  ANSWERS_V2_ALL   : list[str|None]   정답 글자. 정답 없는 갈래는 None
  SOURCES_V2_ALL   : list[str]        어느 모듈에서 왔는지(solver/open/deduce)

작성일: 2026-11-09
"""

from __future__ import annotations

from questions_v2 import QUESTIONS_V2, FAMILIES_V2, ANSWERS_V2
from questions_v2_open import QUESTIONS_OPEN, FAMILIES_OPEN, ANSWERS_OPEN
from questions_v2_deduce import QUESTIONS_DED, FAMILIES_DED, ANSWERS_DED

_PARTS = [
    ("solver", QUESTIONS_V2, FAMILIES_V2, ANSWERS_V2),
    ("open", QUESTIONS_OPEN, FAMILIES_OPEN, ANSWERS_OPEN),
    ("deduce", QUESTIONS_DED, FAMILIES_DED, ANSWERS_DED),
]

QUESTIONS_V2_ALL: list[str] = []
FAMILIES_V2_ALL: list[str] = []
ANSWERS_V2_ALL: list = []
SOURCES_V2_ALL: list[str] = []

for _src, _qs, _fs, _as in _PARTS:
    # 세 리스트의 길이가 어긋나면 q_idx 와 템플릿 id 가 밀려서 분석이 통째로 틀어진다.
    # 조용히 틀리느니 import 단계에서 멈춘다.
    if not (len(_qs) == len(_fs) == len(_as)):
        raise RuntimeError(
            f"{_src}: 길이 불일치 q={len(_qs)} fam={len(_fs)} ans={len(_as)}")
    QUESTIONS_V2_ALL.extend(_qs)
    FAMILIES_V2_ALL.extend(_fs)
    ANSWERS_V2_ALL.extend(_as)
    SOURCES_V2_ALL.extend([_src] * len(_qs))


def family_of(q_idx: int) -> str:
    """문항 번호로 템플릿 id 를 돌려준다. 분석 쪽에서 클러스터 묶을 때 쓴다."""
    return FAMILIES_V2_ALL[q_idx]


def summary():
    """구성 요약 — 문항 수, 템플릿 수, 갈래별 분포."""
    from collections import Counter
    src = Counter(SOURCES_V2_ALL)
    fam = Counter(FAMILIES_V2_ALL)
    # 템플릿당 변형 수가 1이면 문항 자체가 클러스터다(페르미·딜레마 등).
    singles = sum(1 for c in fam.values() if c == 1)
    return {
        "문항": len(QUESTIONS_V2_ALL),
        "템플릿": len(fam),
        "단일문항템플릿": singles,
        "출처별": dict(src),
        "정답있음": sum(1 for a in ANSWERS_V2_ALL if a is not None),
    }


if __name__ == "__main__":
    import sys
    from collections import Counter

    s = summary()
    print(f"문항 {s['문항']}개 / 템플릿 {s['템플릿']}개 "
          f"(그중 단일문항 템플릿 {s['단일문항템플릿']}개)")
    print(f"출처별: {s['출처별']}")
    print(f"정답 있는 문항: {s['정답있음']} / 나머지는 채점하지 않는다")

    bad = 0
    if len(QUESTIONS_V2_ALL) != len(set(QUESTIONS_V2_ALL)):
        dup = [q for q, c in Counter(QUESTIONS_V2_ALL).items() if c > 1]
        print(f"  실패: 모듈 간 중복 문항 {len(dup)}건")
        for q in dup[:5]:
            print(f"    {q[:60]}")
        bad += 1

    # 선택지 A~D 가 다 있는지 — 하나라도 빠지면 모델이 답할 글자가 없다
    miss = [q for q in QUESTIONS_V2_ALL if not all(f"{c})" in q for c in "ABCD")]
    if miss:
        print(f"  실패: 선택지 누락 {len(miss)}건 — {miss[0][:60]}")
        bad += 1

    print("\n통합 검사 " + ("통과" if bad == 0 else f"실패 {bad}건"))
    sys.exit(1 if bad else 0)
