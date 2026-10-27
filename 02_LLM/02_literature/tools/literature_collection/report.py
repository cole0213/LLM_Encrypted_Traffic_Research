"""
report.py — manifest.csv 및 마크다운 리포트 생성.

목적: DB(SSOT)에서 매번 사용자용 산출물을 재생성한다(마스터 프롬프트 18장).
      scope A이므로 다운로드/검증 컬럼은 비운다.
입력: DB 연결, run_id, 출력 경로.
출력: manifest.csv, collection_report_<run>.md, coverage_report_<run>.md.
작성일: 2026-08-22
"""

import csv
from pathlib import Path

MANIFEST_COLS = [
    "project_id", "paper_key", "doi", "arxiv_id", "openalex_id", "title",
    "year", "venue", "work_type", "relevance", "relevance_score",
    "matched_rq", "is_oa", "oa_url", "cited_by_count", "discovered_by",
    "discovery_query", "status_group", "reason_code",
]


def write_manifest(conn, project_id: str, out_csv: Path):
    """papers 테이블 전체를 manifest.csv로 원자적 저장한다."""
    rows = conn.execute("""
        SELECT * FROM papers
        ORDER BY relevance_score DESC, cited_by_count DESC
    """).fetchall()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(MANIFEST_COLS)
        for r in rows:
            w.writerow([
                project_id, r["paper_key"], r["doi"], r["arxiv_id"],
                r["openalex_id"], r["title"], r["year"], r["venue"],
                r["work_type"], r["relevance"], r["relevance_score"],
                r["matched_rq"], r["is_oa"], r["oa_url"], r["cited_by_count"],
                r["discovered_by"], r["discovery_query"], r["status_group"],
                r["reason_code"],
            ])
    tmp.replace(out_csv)
    return len(rows)


def _counts(conn):
    """관련성/소스별 집계를 반환한다."""
    rel = dict(conn.execute(
        "SELECT relevance, COUNT(*) FROM papers GROUP BY relevance").fetchall())
    total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    oa = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE is_oa=1").fetchone()[0]
    year = conn.execute("""
        SELECT year, COUNT(*) FROM papers WHERE year IS NOT NULL
        GROUP BY year ORDER BY year DESC""").fetchall()
    return total, oa, rel, year


def write_reports(conn, cfg, run_id: str, report_dir: Path):
    """collection·coverage 마크다운 리포트를 생성한다."""
    report_dir.mkdir(parents=True, exist_ok=True)
    total, oa, rel, year = _counts(conn)
    pid = cfg["project"]["project_id"]

    # --- collection report ---
    lines = [
        f"# Literature Collection Report — {pid}",
        "",
        f"- Run ID: `{run_id}`",
        f"- Scope: metadata_only (PDF 다운로드 없음)",
        f"- Total unique papers: **{total}**",
        f"- Open-access 표시(OA): {oa}",
        "",
        "## 관련성 분포",
        "| relevance | count |",
        "|---|---:|",
    ]
    for lab in ["core", "method", "background", "unclear", "noise"]:
        lines.append(f"| {lab} | {rel.get(lab, 0)} |")
    lines += ["", "## RQ별 상위 core/method 논문 (score 순)", ""]

    top = conn.execute("""
        SELECT title, year, venue, relevance, relevance_score, matched_rq,
               doi, arxiv_id, cited_by_count
        FROM papers WHERE relevance IN ('core','method')
        ORDER BY relevance_score DESC, cited_by_count DESC LIMIT 40
    """).fetchall()
    lines += ["| # | title | year | rel | score | RQ | cites | id |",
              "|---:|---|---:|---|---:|---|---:|---|"]
    for i, r in enumerate(top, 1):
        ident = r["doi"] or r["arxiv_id"] or ""
        t = (r["title"] or "").replace("|", "/")[:90]
        lines.append(
            f"| {i} | {t} | {r['year'] or ''} | {r['relevance']} | "
            f"{r['relevance_score']} | {r['matched_rq'] or ''} | "
            f"{r['cited_by_count'] or ''} | {ident} |")
    _atomic_write(report_dir / f"collection_report_{run_id}.md",
                  "\n".join(lines) + "\n")

    # --- coverage report ---
    cov = [f"# Coverage Report — {pid}", "", f"- Run ID: `{run_id}`",
           f"- Total: {total}", "", "## 연도별 분포", "| year | count |",
           "|---:|---:|"]
    for y, c in year:
        cov.append(f"| {y} | {c} |")
    cov += ["", "## RQ 매칭 커버리지 (core+method 기준)", "| RQ | papers |",
            "|---|---:|"]
    for rq in ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6"]:
        n = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE relevance IN ('core','method') "
            "AND matched_rq LIKE ?", (f"%{rq}%",)).fetchone()[0]
        cov.append(f"| {rq} | {n} |")
    _atomic_write(report_dir / f"coverage_report_{run_id}.md",
                  "\n".join(cov) + "\n")

    return {"total": total, "oa": oa, "relevance": rel}


def _atomic_write(path: Path, text: str):
    """tmp 후 replace로 원자적 기록."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    tmp.replace(path)
