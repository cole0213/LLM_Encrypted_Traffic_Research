"""
discovery/openalex.py — OpenAlex 검색 어댑터.

목적: 주제 검색으로 후보 논문 메타데이터를 가져온다. OpenAlex는 무키로도
      동작하며(polite pool은 mailto 사용), 초록(inverted index)·인용수·OA
      상태·work type을 함께 준다. CS/네트워킹 주제 커버리지가 넓다.
입력: 검색어, from_year, limit, mailto.
출력: 정규화된 후보 레코드 리스트.
작성일: 2026-08-22
"""

from .. import httpclient

BASE = "https://api.openalex.org/works"


def _reconstruct_abstract(inv: dict | None) -> str | None:
    """OpenAlex의 abstract_inverted_index를 평문 초록으로 복원한다."""
    if not inv:
        return None
    # {단어: [위치,...]} → 위치순 배열.
    positions = []
    for word, locs in inv.items():
        for p in locs:
            positions.append((p, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def search(query: str, from_year: int, limit: int, mailto: str,
           user_agent: str, timeout: int, retry_max: int,
           backoff_base: float) -> tuple[int, list[dict]]:
    """OpenAlex works 검색. (http_status, 레코드리스트) 반환."""
    params = {
        "search": query,
        "filter": f"from_publication_date:{from_year}-01-01",
        "per_page": min(limit, 200),
        "mailto": mailto,
    }
    headers = {"User-Agent": user_agent}
    status, data = httpclient.get(
        BASE, params=params, headers=headers, timeout=timeout,
        retry_max=retry_max, backoff_base=backoff_base, expect="json",
    )
    records = []
    for w in data.get("results", [])[:limit]:
        doi = w.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "")
        # 저자 이름 리스트.
        authors = [a.get("author", {}).get("display_name")
                   for a in w.get("authorships", [])]
        # arXiv ID 추출(있으면).
        arxiv_id = None
        for loc in w.get("locations", []) or []:
            src = (loc.get("source") or {})
            if src and "arxiv" in (src.get("display_name") or "").lower():
                lp = loc.get("landing_page_url") or ""
                arxiv_id = lp.rsplit("/", 1)[-1] or None
        oa = w.get("open_access", {}) or {}
        records.append({
            "doi": doi,
            "arxiv_id": arxiv_id,
            "openalex_id": w.get("id"),
            "title": w.get("display_name"),
            "year": w.get("publication_year"),
            "authors": [a for a in authors if a],
            "venue": ((w.get("primary_location") or {}).get("source") or {})
                      .get("display_name"),
            "work_type": w.get("type"),
            "abstract": _reconstruct_abstract(
                w.get("abstract_inverted_index")),
            "cited_by_count": w.get("cited_by_count"),
            "is_oa": bool(oa.get("is_oa")),
            "oa_url": oa.get("oa_url"),
            "source": "openalex",
        })
    return status, records
