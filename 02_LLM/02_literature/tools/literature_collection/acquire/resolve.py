"""
acquire/resolve.py — 논문 레코드 → 합법 OA PDF URL 후보.

목적: arXiv 직접 PDF, arXiv-DOI, Unpaywall(OA 위치)로 다운로드 가능한 PDF
      URL을 우선순위대로 만든다. OA만 다룬다(마스터 프롬프트 7장·oa_only).
입력: 논문 dict(doi, arxiv_id), 이메일.
출력: [(url, source_note), ...] 우선순위 리스트.
작성일: 2026-08-22
"""

import re

from .. import httpclient

UNPAYWALL = "https://api.unpaywall.org/v2/"


def _arxiv_id_from_doi(doi: str | None) -> str | None:
    """arXiv-DOI(10.48550/arxiv.XXXX)에서 arXiv id 추출."""
    if not doi:
        return None
    m = re.match(r"10\.48550/arxiv\.(.+)", doi)
    return m.group(1) if m else None


def candidates(paper: dict, email: str, ua: str, timeout: int) -> list[tuple]:
    """다운로드 시도할 (url, note) 후보를 우선순위대로 반환한다."""
    out = []
    doi = paper.get("doi")
    arxiv_id = paper.get("arxiv_id")

    # 1) 순수 arXiv 논문 → 직접 PDF.
    aid = arxiv_id or _arxiv_id_from_doi(doi)
    if aid:
        # 일부 소스가 id 앞에 'arxiv.'/'arxiv:'를 붙여 저장하는 경우 정리.
        aid = re.sub(r"(?i)^\s*arxiv[:.]", "", aid).strip()
        if aid:
            out.append((f"https://arxiv.org/pdf/{aid}", "arxiv_direct"))

    # 2) Unpaywall OA 위치(arXiv-DOI가 아닌 실제 저널 DOI에 한해).
    if doi and not doi.startswith("10.48550/arxiv."):
        try:
            _, data = httpclient.get(
                UNPAYWALL + doi, params={"email": email},
                headers={"User-Agent": ua}, timeout=timeout,
                retry_max=3, backoff_base=2.0, expect="json")
            locs = []
            best = data.get("best_oa_location")
            if best:
                locs.append(best)
            locs += data.get("oa_locations", []) or []
            for loc in locs:
                url = loc.get("url_for_pdf") or loc.get("url")
                if url:
                    out.append((url, "unpaywall:" +
                                (loc.get("host_type") or "?")))
        except Exception as e:
            out.append((None, f"unpaywall_error:{type(e).__name__}"))

    # 중복 URL 제거(순서 보존).
    seen, uniq = set(), []
    for url, note in out:
        if url and url not in seen:
            seen.add(url)
            uniq.append((url, note))
        elif url is None:
            uniq.append((url, note))  # 에러 노트는 진단용 유지
    return uniq
