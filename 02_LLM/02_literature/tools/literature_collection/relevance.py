"""
relevance.py — 규칙 기반 관련성 게이트.

목적: 발견된 후보를 core/method/background/noise/unclear로 분류해 노이즈
      다운로드를 막는다(마스터 프롬프트 6.3). LLM 없이 제목+초록 키워드
      점수화로 판정한다. scope A는 다운로드가 없지만, 리포트 우선순위와
      향후 다운로드 게이트에 그대로 쓰인다.
입력: 제목, 초록.
출력: (relevance 라벨, score[0~1], 근거 태그).
작성일: 2026-08-22
"""

# 트래픽/네트워크 도메인 신호 — 이게 없으면 주제 무관(noise) 취급.
TRAFFIC_TERMS = [
    "traffic", "network flow", "packet", "flow-based", "netflow",
    "fingerprint", "encrypted traffic", "tls", "quic", "sni", "tor",
    "vpn", "pcap", "side channel", "side-channel", "netowrk",  # 흔한 오타 방어
]

# 생성형 AI / 대화형 스트리밍 신호 — core 승격 요인.
GENAI_TERMS = [
    "llm", "large language model", "chatbot", "chat bot", "generative ai",
    "chatgpt", "gpt-", "copilot", "gemini", "claude", "conversational ai",
    "token streaming", "server-sent event", "prompt", "language model",
]

# 방법론/분류 기여 신호 — method 판정 요인.
METHOD_TERMS = [
    "classification", "classifier", "deep learning", "transformer",
    "representation learning", "pre-trained", "pretrained", "bert",
    "feature", "detection", "identification", "generalization",
    "concept drift", "cross-dataset", "dataset", "benchmark",
]

# 명백한 주제 이탈 — noise 강등(트래픽 신호 없을 때만 적용).
OFFTOPIC_TERMS = [
    "cancer", "clinical", "protein", "molecule", "galaxy", "seismic",
    "agriculture", "sentiment analysis", "machine translation",
]

# "LLM을 도구로 쓴" 신호 — 우리 타깃(GenAI 트래픽=식별 대상)이 아니라
# LLM으로 침입탐지/합성/증강을 하는 논문. core에서 method로 강등한다.
TOOL_USE_TERMS = [
    "intrusion detection", "malicious traffic", "anomaly detection",
    "synthetic", "augmentation", "wgan", "gan ", "zero-day",
    "threat detection", "llm-based", "llm-oriented", "llm-driven",
    "powered", "using large language", "using llm", "for network security",
    "generating", "generation of", "ids",
]

# GenAI 트래픽이 '식별 대상'임을 가리키는 신호 — 있으면 진짜 core.
TARGET_SIGNAL_TERMS = [
    "fingerprint", "chatbot traffic", "llm traffic", "conversational",
    "token streaming", "server-sent", "service identification",
    "identify chatgpt", "detecting chatgpt", "detect llm", "identifying llm",
    "traffic of", "usage detection",
]


def _count_hits(text: str, terms: list[str]) -> list[str]:
    """text 안에 등장한 term 목록을 반환한다(소문자 부분일치)."""
    return [t for t in terms if t in text]


def classify(title: str, abstract: str | None) -> tuple[str, float, str]:
    """후보의 관련성 라벨·점수·근거를 반환한다.

    규칙:
      - 트래픽 도메인 신호 없음 → noise (또는 정보부족 시 unclear).
      - 트래픽 + GenAI 신호 → core.
      - 트래픽 + 방법론 신호 → method.
      - 트래픽만 약하게 → background.
    """
    text = (title + " \n " + (abstract or "")).lower()
    traffic = _count_hits(text, TRAFFIC_TERMS)
    genai = _count_hits(text, GENAI_TERMS)
    method = _count_hits(text, METHOD_TERMS)
    offtopic = _count_hits(text, OFFTOPIC_TERMS)

    tags = []
    if traffic:
        tags.append("traffic:" + ",".join(traffic[:3]))
    if genai:
        tags.append("genai:" + ",".join(genai[:3]))
    if method:
        tags.append("method:" + ",".join(method[:3]))
    reason = "; ".join(tags)

    # 트래픽 도메인 신호 부재 → 주제 무관.
    if not traffic:
        if not abstract:
            return "unclear", 0.1, "no traffic term; no abstract"
        return "noise", 0.0, reason or "no traffic-domain term"

    # 트래픽 있으나 명백한 타 분야 용어가 지배적이면 noise.
    if offtopic and not genai and not method:
        return "noise", 0.1, "offtopic:" + ",".join(offtopic[:3])

    # 점수: 트래픽 기반 + genai/method 가중.
    score = 0.4 + 0.15 * min(len(traffic), 3) / 3
    score += 0.35 * min(len(genai), 2) / 2
    score += 0.15 * min(len(method), 3) / 3
    score = round(min(score, 1.0), 3)

    if genai:
        target = _count_hits(text, TARGET_SIGNAL_TERMS)
        tool = _count_hits(text, TOOL_USE_TERMS)
        if target:
            # GenAI 트래픽이 식별 대상 → 진짜 core.
            return "core", max(score, 0.85), reason + "; TARGET:" + \
                ",".join(target[:2])
        if tool:
            # LLM을 도구로 사용(IDS·합성 등) → 방법론 참고, core 아님.
            return "method", max(score, 0.6), reason + "; TOOL_USE:" + \
                ",".join(tool[:2])
        return "core", max(score, 0.8), reason
    if method:
        return "method", max(score, 0.55), reason
    return "background", min(score, 0.5), reason
