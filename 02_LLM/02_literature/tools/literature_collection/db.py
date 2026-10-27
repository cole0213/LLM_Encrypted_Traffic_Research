"""
db.py — SQLite 상태 저장소(SSOT).

목적: 발견된 논문·실행 이력을 멱등적으로 저장한다. 재실행 시 UPSERT로
      기존 레코드를 갱신하고 중복을 막는다. 마스터 프롬프트 3장 스키마의
      scope A(메타데이터 발견) 부분집합.
입력: DB 경로, 논문 dict.
출력: literature.db.
작성일: 2026-08-22
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    paper_key          TEXT PRIMARY KEY,
    doi                TEXT,
    arxiv_id           TEXT,
    arxiv_canonical    TEXT,
    openalex_id        TEXT,
    title              TEXT,
    title_norm         TEXT,
    year               INTEGER,
    authors_json       TEXT,
    venue              TEXT,
    work_type          TEXT,
    abstract           TEXT,
    cited_by_count     INTEGER,
    is_oa              INTEGER,
    oa_url             TEXT,
    relevance          TEXT,
    relevance_score    REAL,
    matched_rq         TEXT,
    discovered_by      TEXT,
    discovery_query    TEXT,
    status_group       TEXT,
    reason_code        TEXT,
    created_at         TEXT,
    updated_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_relevance ON papers(relevance);

CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,
    project_id     TEXT,
    config_hash    TEXT,
    scope          TEXT,
    os             TEXT,
    python_version TEXT,
    started_at     TEXT,
    ended_at       TEXT,
    status         TEXT,
    stats_json     TEXT
);

CREATE TABLE IF NOT EXISTS discovery_log (
    run_id       TEXT,
    source       TEXT,
    query        TEXT,
    matched_rq   TEXT,
    returned     INTEGER,
    new_papers   INTEGER,
    http_status  INTEGER,
    error        TEXT,
    ts           TEXT
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """DB에 연결하고 스키마를 보장한다."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# UPSERT 대상 컬럼 — paper_key 제외 전 필드.
_UPSERT_COLS = [
    "doi", "arxiv_id", "arxiv_canonical", "openalex_id", "title", "title_norm",
    "year", "authors_json", "venue", "work_type", "abstract", "cited_by_count",
    "is_oa", "oa_url", "relevance", "relevance_score", "matched_rq",
    "discovered_by", "discovery_query", "status_group", "reason_code",
    "created_at", "updated_at",
]


def upsert_paper(conn: sqlite3.Connection, rec: dict) -> bool:
    """논문 레코드를 UPSERT한다. 신규면 True, 기존 갱신이면 False.

    기존 레코드가 있으면 발견 경로(discovered_by/discovery_query)를 누적하고
    관련성 점수가 더 높으면 갱신한다. created_at은 보존한다.
    """
    key = rec["paper_key"]
    cur = conn.execute("SELECT * FROM papers WHERE paper_key=?", (key,))
    existing = cur.fetchone()
    if existing is None:
        cols = ["paper_key"] + _UPSERT_COLS
        placeholders = ",".join(["?"] * len(cols))
        vals = [key] + [rec.get(c) for c in _UPSERT_COLS]
        conn.execute(
            f"INSERT INTO papers ({','.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        return True
    # 기존 갱신: 발견 경로 병합, 더 높은 관련성 점수 채택.
    merged_by = _merge_csv(existing["discovered_by"], rec.get("discovered_by"))
    merged_q = _merge_csv(existing["discovery_query"], rec.get("discovery_query"))
    merged_rq = _merge_csv(existing["matched_rq"], rec.get("matched_rq"))
    old_score = existing["relevance_score"] or 0.0
    new_score = rec.get("relevance_score") or 0.0
    if new_score > old_score:
        relevance = rec.get("relevance")
        score = new_score
    else:
        relevance = existing["relevance"]
        score = old_score
    conn.execute(
        """UPDATE papers SET discovered_by=?, discovery_query=?, matched_rq=?,
               relevance=?, relevance_score=?, updated_at=?,
               abstract=COALESCE(abstract, ?), oa_url=COALESCE(oa_url, ?)
           WHERE paper_key=?""",
        (merged_by, merged_q, merged_rq, relevance, score,
         rec.get("updated_at"), rec.get("abstract"), rec.get("oa_url"), key),
    )
    return False


def _merge_csv(old: str | None, new: str | None) -> str:
    """콤마구분 값 집합을 합쳐 정렬 반환한다(중복 제거)."""
    items = set()
    for v in (old, new):
        if v:
            items.update(x.strip() for x in v.split("|") if x.strip())
    return "|".join(sorted(items))


def start_run(conn, run_id, project_id, config_hash, scope, os_name,
              py_ver, started_at):
    """run 레코드를 시작 상태로 기록한다."""
    conn.execute(
        """INSERT OR REPLACE INTO runs
           (run_id, project_id, config_hash, scope, os, python_version,
            started_at, status)
           VALUES (?,?,?,?,?,?,?, 'running')""",
        (run_id, project_id, config_hash, scope, os_name, py_ver, started_at),
    )
    conn.commit()


def finish_run(conn, run_id, ended_at, stats_json):
    """run 레코드를 완료 상태로 갱신한다."""
    conn.execute(
        "UPDATE runs SET ended_at=?, status='done', stats_json=? WHERE run_id=?",
        (ended_at, stats_json, run_id),
    )
    conn.commit()


def log_discovery(conn, row: dict):
    """소스·쿼리별 발견 로그 한 줄을 기록한다."""
    conn.execute(
        """INSERT INTO discovery_log
           (run_id, source, query, matched_rq, returned, new_papers,
            http_status, error, ts)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (row.get("run_id"), row.get("source"), row.get("query"),
         row.get("matched_rq"), row.get("returned"), row.get("new_papers"),
         row.get("http_status"), row.get("error"), row.get("ts")),
    )
    conn.commit()
