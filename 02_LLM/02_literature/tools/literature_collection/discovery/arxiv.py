"""
discovery/arxiv.py — arXiv Atom API 검색 어댑터.

목적: 프리프린트(트래픽/CS 논문 다수가 arXiv에 선공개)를 발견한다.
      arXiv legacy API는 단일 연결·요청간 최소 3초 권장(마스터 프롬프트 11.1).
입력: 검색어, limit.
출력: 정규화된 후보 레코드 리스트.
작성일: 2026-08-22
"""

import xml.etree.ElementTree as ET

from .. import httpclient

BASE = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom",
      "arxiv": "http://arxiv.org/schemas/atom"}


def search(query: str, limit: int, user_agent: str, timeout: int,
           retry_max: int, backoff_base: float) -> tuple[int, list[dict]]:
    """arXiv 검색. (http_status, 레코드리스트) 반환."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit, 100),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    headers = {"User-Agent": user_agent}
    status, text = httpclient.get(
        BASE, params=params, headers=headers, timeout=timeout,
        retry_max=retry_max, backoff_base=backoff_base, expect="text",
    )
    root = ET.fromstring(text)
    records = []
    for entry in root.findall("a:entry", NS):
        raw_id = (entry.findtext("a:id", default="", namespaces=NS) or "")
        # id = http://arxiv.org/abs/XXXX.YYYYYvN
        arxiv_id = raw_id.rsplit("/", 1)[-1] if raw_id else None
        title = (entry.findtext("a:title", default="", namespaces=NS) or
                 "").strip().replace("\n", " ")
        summary = (entry.findtext("a:summary", default="", namespaces=NS) or
                   "").strip().replace("\n", " ")
        published = entry.findtext("a:published", default="", namespaces=NS)
        year = None
        if published and len(published) >= 4:
            year = int(published[:4])
        authors = [a.findtext("a:name", default="", namespaces=NS)
                   for a in entry.findall("a:author", NS)]
        # DOI가 붙은 경우(저널 출판됨).
        doi = entry.findtext("arxiv:doi", default=None, namespaces=NS)
        records.append({
            "doi": doi,
            "arxiv_id": arxiv_id,
            "openalex_id": None,
            "title": title,
            "year": year,
            "authors": [a for a in authors if a],
            "venue": "arXiv",
            "work_type": "preprint",
            "abstract": summary,
            "cited_by_count": None,
            "is_oa": True,           # arXiv은 항상 공개.
            "oa_url": raw_id.replace("/abs/", "/pdf/") if raw_id else None,
            "source": "arxiv",
        })
    return status, records
