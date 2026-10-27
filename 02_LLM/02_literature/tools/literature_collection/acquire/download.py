"""
acquire/download.py — PDF 스트리밍 다운로드 + 원자적 저장.

목적: 후보 URL에서 PDF를 .part로 받아 검증 통과 시 최종 이름으로 rename
      한다(마스터 프롬프트 9.1). HTML 오응답은 검증에서 걸러진다.
입력: url, 저장 경로.
출력: dict(ok, http_status, content_type, bytes, reason).
작성일: 2026-08-22
"""

from pathlib import Path

import requests

from ..validate import pdf as pdfval

_session = requests.Session()


def fetch(url: str, dest: Path, ua: str, timeout: int,
          max_mb: int = 250) -> dict:
    """url에서 PDF를 받아 dest에 저장(검증 통과 시)."""
    dest = Path(dest)
    part = dest.with_suffix(".part")
    headers = {"User-Agent": ua, "Accept": "application/pdf,*/*"}
    try:
        with _session.get(url, headers=headers, timeout=timeout,
                          stream=True, allow_redirects=True) as r:
            status = r.status_code
            ctype = r.headers.get("Content-Type", "")
            if status != 200:
                return {"ok": False, "http_status": status,
                        "content_type": ctype, "bytes": 0,
                        "reason": f"http_{status}"}
            total = 0
            limit = max_mb * 1024 * 1024
            with open(part, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > limit:
                        f.close()
                        part.unlink(missing_ok=True)
                        return {"ok": False, "http_status": status,
                                "content_type": ctype, "bytes": total,
                                "reason": "oversized"}
                    f.write(chunk)
    except requests.RequestException as e:
        part.unlink(missing_ok=True)
        return {"ok": False, "http_status": 0, "content_type": "",
                "bytes": 0, "reason": f"neterror:{type(e).__name__}"}

    # 검증 후 원자적 rename.
    v = pdfval.validate(part)
    if not v["ok"]:
        part.replace(dest.with_suffix(".rejected"))  # 격리
        return {"ok": False, "http_status": status, "content_type": ctype,
                "bytes": total, "reason": v["reason"]}
    part.replace(dest)
    return {"ok": True, "http_status": status, "content_type": ctype,
            "bytes": total, "reason": "ok", "sha256": v["sha256"],
            "page_count": v["page_count"]}
