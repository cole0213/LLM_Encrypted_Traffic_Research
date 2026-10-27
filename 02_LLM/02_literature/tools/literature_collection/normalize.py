"""
normalize.py — 식별자·제목 정규화 유틸.

목적: DOI/arXiv ID/제목을 일관된 canonical 형태로 바꿔 중복 제거(dedup)와
      교차 매칭을 안정화한다. 마스터 프롬프트 5장(식별자 정규화) 규칙 구현.
입력: 원시 DOI/arXiv 문자열, 제목 문자열.
출력: 정규화된 문자열, paper_key.
작성일: 2026-08-22
"""

import re
import unicodedata
import hashlib


def normalize_doi(raw: str | None) -> str | None:
    """DOI를 소문자 canonical 형태로 정규화한다.

    접두어(https://doi.org/, doi: 등)를 벗기고 NFKC 정규화·소문자화한다.
    DOI suffix의 괄호/슬래시/콜론은 DOI 일부일 수 있어 임의 삭제하지 않는다.
    """
    if not raw:
        return None
    s = raw.strip()
    s = re.sub(r"(?i)^\s*(https?://(dx\.)?doi\.org/|doi:)", "", s)
    s = unicodedata.normalize("NFKC", s)
    s = s.strip().strip(".,;")
    s = s.lower()
    if not s.startswith("10."):
        return None  # 유효 DOI 형태 아님
    return s


def normalize_arxiv(raw: str | None) -> tuple[str | None, str | None]:
    """arXiv ID를 (원본_버전포함, canonical_버전제거)로 반환한다.

    dedup은 canonical로, 다운로드 버전은 원본으로 쓴다.
    """
    if not raw:
        return None, None
    s = raw.strip()
    s = re.sub(r"(?i)^\s*(https?://arxiv\.org/(abs|pdf)/|arxiv:)", "", s)
    s = s.replace(".pdf", "").strip()
    if not s:
        return None, None
    canonical = re.sub(r"v\d+$", "", s)  # 뒤쪽 버전 태그 제거
    return s, canonical


def normalize_title(title: str | None) -> str:
    """제목을 fuzzy 매칭용으로 정규화한다(소문자·영숫자만·공백 단일화)."""
    if not title:
        return ""
    s = unicodedata.normalize("NFKC", title).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def paper_key(doi: str | None, arxiv_canonical: str | None,
              title_norm: str | None) -> str:
    """레코드의 안정적 primary key를 만든다.

    우선순위: DOI > arXiv canonical > 제목 해시. 같은 논문이면 항상 같은 key.
    """
    if doi:
        return "doi:" + doi
    if arxiv_canonical:
        return "arxiv:" + arxiv_canonical
    h = hashlib.sha1((title_norm or "").encode("utf-8")).hexdigest()[:16]
    return "title:" + h
