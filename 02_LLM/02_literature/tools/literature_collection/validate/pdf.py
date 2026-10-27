"""
validate/pdf.py — 내려받은 파일이 진짜 PDF인지 검증.

목적: Content-Type만 믿지 않고 매직바이트·파서·페이지수로 확인한다
      (마스터 프롬프트 12장). HTML/JSON masquerade를 걸러낸다.
입력: 파일 경로.
출력: dict(ok, page_count, sha256, reason).
작성일: 2026-08-22
"""

import hashlib
from pathlib import Path

from pypdf import PdfReader


def validate(path: str | Path) -> dict:
    """PDF 파일을 검증한다. ok=True면 통과."""
    path = Path(path)
    data = path.read_bytes()
    if len(data) < 1024:
        return {"ok": False, "reason": "too_small",
                "sha256": None, "page_count": 0}
    # 매직바이트 — startswith로 길이 불일치 비교 회피.
    if not data.startswith(b"%PDF-"):
        return {"ok": False, "reason": "invalid_magic",
                "sha256": None, "page_count": 0}
    sha = hashlib.sha256(data).hexdigest()
    try:
        reader = PdfReader(str(path))
        n = len(reader.pages)
    except Exception as e:
        return {"ok": False, "reason": f"pdf_parse_error:{type(e).__name__}",
                "sha256": sha, "page_count": 0}
    if n < 1:
        return {"ok": False, "reason": "no_pages", "sha256": sha,
                "page_count": 0}
    return {"ok": True, "reason": "valid", "sha256": sha, "page_count": n}
