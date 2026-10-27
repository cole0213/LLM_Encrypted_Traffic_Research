"""
queries.py — topic/RQ/scope에서 검색 쿼리를 자동 생성.

목적: 입력(seeds/identifiers)이 없을 때 연구주제·RQ·include_scope로부터
      발견용 검색 쿼리를 만든다. 각 쿼리에 관련 RQ 태그를 붙여 발견 계보를
      추적한다(마스터 프롬프트 6.2 검색 쿼리 계보).
입력: 없음(상수 정의). 필요시 config로 확장 가능.
출력: [{"q": 검색어, "rq": 관련 RQ 태그}, ...]
작성일: 2026-08-22
"""

# 각 쿼리는 (검색문자열, 관련 RQ). 트래픽/CS 도메인에 맞춘 영어 쿼리.
# GenAI 트래픽 식별은 신생 주제 → 인접 확립분야(암호화 트래픽 분류,
# website fingerprinting, 부채널)를 넓게 훑어 방법론 근거를 모은다.
QUERIES: list[tuple[str, str]] = [
    # --- 핵심: 생성형 AI / LLM 트래픽 식별 (RQ1, RQ3, RQ5) ---
    ("LLM chatbot network traffic identification", "RQ1,RQ3"),
    ("ChatGPT traffic fingerprinting encrypted", "RQ1,RQ3"),
    ("generative AI service traffic classification", "RQ1,RQ3"),
    ("large language model traffic detection network", "RQ1"),
    ("AI chatbot encrypted traffic analysis", "RQ1,RQ3"),

    # --- 암호화 트래픽 분류·표현학습 (RQ1, 방법론) ---
    ("encrypted traffic classification deep learning", "RQ1"),
    ("encrypted traffic classification transformer", "RQ1"),
    ("network traffic classification pre-trained representation", "RQ1"),
    ("byte-level traffic classification BERT", "RQ1"),
    ("TLS 1.3 encrypted traffic classification", "RQ1,RQ3"),
    ("QUIC traffic classification machine learning", "RQ1,RQ4"),

    # --- 웹사이트/서비스 핑거프린팅 (RQ3, RQ4) ---
    ("website fingerprinting encrypted traffic", "RQ3"),
    ("service identification encrypted traffic SNI", "RQ3"),
    ("mobile app traffic fingerprinting identification", "RQ4"),
    ("application identification network flow features", "RQ4"),

    # --- 스트리밍/대화형 타이밍 부채널 (RQ1, RQ5) ---
    ("streaming service traffic identification timing", "RQ1,RQ5"),
    ("server-sent events traffic analysis", "RQ5"),
    ("token streaming side channel language model", "RQ1,RQ5"),
    ("LLM response length side channel network", "RQ5"),
    ("prompt length inference encrypted traffic", "RQ5"),
    ("keystroke timing side channel encrypted", "RQ5"),
    ("variable length compression side channel leak", "RQ5"),

    # --- 데이터셋·수집 (RQ2) ---
    ("encrypted traffic dataset benchmark classification", "RQ2"),
    ("network traffic dataset LLM chatbot", "RQ2"),
    ("traffic capture labeling methodology dataset", "RQ2"),

    # --- 보편성·일반화·드리프트 (RQ6) ---
    ("traffic classification concept drift generalization", "RQ6"),
    ("cross-dataset generalization traffic classification", "RQ6"),
    ("robust encrypted traffic classification distribution shift", "RQ6"),
]


def generate_queries() -> list[dict]:
    """검색 쿼리 목록을 dict 형태로 반환한다."""
    return [{"q": q, "rq": rq} for q, rq in QUERIES]
