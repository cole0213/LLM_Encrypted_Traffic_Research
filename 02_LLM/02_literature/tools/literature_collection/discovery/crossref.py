"""
discovery/crossref.py — Crossref 검색 어댑터.

목적: DOI 기반 출판물 메타데이터 보강. 식별 가능한 mailto를 붙여 polite
      pool을 쓰고 필요한 필드만 요청한다(마스터 프롬프트 11.1).
입력: 검색어, from_year, limit, mailto.
출력: 정규화된 후보 레코드 리스트.
작성일: 2026-08-22
"""

from .. import httpclient

BASE = "https://api.crossref.org/works"


def search(query: str, from_year: int, limit: int, mailto: str,
           user_agent: str, timeout: int, retry_max: int,
           backoff_base: float) -> tuple[int, list[dict]]:
    """Crossref 검색. (http_status, 레코드리스트) 반환."""
    params = {
        "query": query,
        "rows": min(limit, 100),
        "filter": f"from-pub-date:{from_year}-01-01,type:journal-article",
        "select": "DOI,title,author,issued,container-title,type,abstract",
        "mailto": mailto,
    }
    headers = {"User-Agent": user_agent}
    status, data = httpclient.get(
        BASE, params=params, headers=headers, timeout=timeout,
        retry_max=retry_max, backoff_base=backoff_base, expect="json",
    )
    records = []
    for it in data.get("message", {}).get("items", [])[:limit]:
        title_list = it.get("title") or []
        title = title_list[0] if title_list else None
        if not title:
            continue
        # 발행연도.
        year = None
        issued = (it.get("issued") or {}).get("date-parts") or [[None]]
        if issued and issued[0] and issued[0][0]:
            year = issued[0][0]
        authors = []
        for a in it.get("author", []) or []:
            nm = " ".join(x for x in [a.get("given"), a.get("family")] if x)
            if nm:
                authors.append(nm)
        cont = it.get("container-title") or []
        # Crossref abstract는 JATS XML 태그 포함 → 태그 대충 제거.
        abstract = it.get("abstract")
        if abstract:
            import re
            abstract = re.sub(r"<[^>]+>", " ", abstract)
            abstract = re.sub(r"\s+", " ", abstract).strip()
        records.append({
            "doi": it.get("DOI"),
            "arxiv_id": None,
            "openalex_id": None,
            "title": title,
            "year": year,
            "authors": authors,
            "venue": cont[0] if cont else None,
            "work_type": it.get("type"),
            "abstract": abstract,
            "cited_by_count": None,
            "is_oa": None,       # Crossref만으로 OA 판정 안 함.
            "oa_url": None,
            "source": "crossref",
        })
    return status, records
