"""
tests/test_core.py — 핵심 유닛 테스트 (pytest 불필요).

목적: 정규화·paper_key·관련성·DB 멱등성을 검증한다(마스터 프롬프트 부록 B
      중 scope A 해당분).
사용: python tools/literature_collection/tests/test_core.py
작성일: 2026-08-22
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from literature_collection import normalize as nz
from literature_collection import relevance as rel
from literature_collection import db as dbmod

_passed = 0
_failed = 0


def check(name, cond):
    """단언 결과를 집계·출력."""
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS {name}")
    else:
        _failed += 1
        print(f"  FAIL {name}")


def test_normalize_doi_url():
    check("doi_url_strip",
          nz.normalize_doi("https://doi.org/10.1145/ABC.123") == "10.1145/abc.123")
    check("doi_prefix", nz.normalize_doi("doi:10.1/X") == "10.1/x")
    check("doi_invalid", nz.normalize_doi("not-a-doi") is None)


def test_normalize_doi_with_parentheses():
    # DOI suffix의 괄호는 보존해야 한다.
    check("doi_parens",
          nz.normalize_doi("10.1016/j.x(2020)123") == "10.1016/j.x(2020)123")


def test_arxiv_version_dedup():
    orig, canon = nz.normalize_arxiv("arXiv:2201.12345v3")
    check("arxiv_orig", orig == "2201.12345v3")
    check("arxiv_canon", canon == "2201.12345")
    o2, c2 = nz.normalize_arxiv("https://arxiv.org/abs/2201.12345")
    check("arxiv_dedup_same_key", c2 == canon)


def test_paper_key_priority():
    k_doi = nz.paper_key("10.1/x", "2201.1", "title")
    check("key_doi_priority", k_doi == "doi:10.1/x")
    k_arx = nz.paper_key(None, "2201.1", "title")
    check("key_arxiv", k_arx == "arxiv:2201.1")
    k_title = nz.paper_key(None, None, "some title")
    check("key_title", k_title.startswith("title:"))


def test_relevance_classify():
    core, s1, _ = rel.classify(
        "Fingerprinting LLM chatbot traffic over encrypted TLS", None)
    check("relevance_core", core == "core" and s1 >= 0.8)
    method, _, _ = rel.classify(
        "Encrypted traffic classification with transformers", None)
    check("relevance_method", method in ("method", "core"))
    noise, _, _ = rel.classify(
        "Deep learning for protein folding prediction", "protein molecule")
    check("relevance_noise", noise == "noise")
    # LLM을 도구로 쓴 IDS 논문은 core 아니라 method로 강등돼야 한다.
    tool, _, _ = rel.classify(
        "LLM-based intrusion detection for network traffic", None)
    check("relevance_tool_use_demoted", tool == "method")


def test_db_upsert_idempotent():
    with tempfile.TemporaryDirectory() as td:
        conn = dbmod.connect(Path(td) / "t.db")
        rec = {"paper_key": "doi:10.1/x", "doi": "10.1/x", "title": "T",
               "relevance": "core", "relevance_score": 0.9,
               "discovered_by": "openalex", "discovery_query": "q1",
               "matched_rq": "RQ1", "created_at": "t", "updated_at": "t"}
        for k in dbmod._UPSERT_COLS:
            rec.setdefault(k, None)
        n1 = dbmod.upsert_paper(conn, rec)
        # 두 번째: 다른 소스로 재발견 → 신규 아님, 경로 병합.
        rec2 = dict(rec, discovered_by="arxiv", discovery_query="q2")
        n2 = dbmod.upsert_paper(conn, rec2)
        row = conn.execute(
            "SELECT discovered_by, discovery_query FROM papers").fetchone()
        check("upsert_first_new", n1 is True)
        check("upsert_second_not_new", n2 is False)
        check("upsert_merge_source", "arxiv" in row["discovered_by"]
              and "openalex" in row["discovered_by"])
        count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        check("upsert_single_row", count == 1)
        conn.close()


def main():
    for fn in [test_normalize_doi_url, test_normalize_doi_with_parentheses,
               test_arxiv_version_dedup, test_paper_key_priority,
               test_relevance_classify, test_db_upsert_idempotent]:
        print(f"[{fn.__name__}]")
        fn()
    print(f"\n== {_passed} passed, {_failed} failed ==")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
