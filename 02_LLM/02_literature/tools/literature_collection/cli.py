"""
cli.py — 문헌 발견 파이프라인 진입점 (scope A: 메타데이터만).

목적: config를 읽고 topic 쿼리로 OpenAlex/arXiv/Crossref를 훑어 후보를
      정규화·관련성 분류·DB 저장하고 리포트를 생성한다. 멱등적(재실행 시
      UPSERT)이며 소스별 polite 간격을 지킨다.
사용:
    python -m literature_collection.cli discover --config config/collection.yaml
    python -m literature_collection.cli report   --config config/collection.yaml
입력: collection.yaml.
출력: literature.db, manifest.csv, 리포트.
작성일: 2026-08-22
"""

import sys
import json
import time
import argparse
import platform
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# 패키지 상대 import 지원(스크립트 직접 실행 대비).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "literature_collection"

from . import config as cfgmod
from . import db as dbmod
from . import normalize as nz
from . import relevance as rel
from . import report as rep
from .queries import generate_queries
from .discovery import openalex, arxiv, crossref
from .acquire import resolve as resolvemod
from .acquire import download as dlmod
from .httpclient import HttpError


def _now() -> str:
    """UTC ISO 타임스탬프."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    """run_id = 시각 + 짧은 해시."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    h = hashlib.sha1(ts.encode()).hexdigest()[:6]
    return f"{ts}_{h}"


def _to_record(raw: dict, query: str, rq: str) -> dict:
    """어댑터 출력(raw)을 DB 레코드로 정규화·분류한다."""
    doi = nz.normalize_doi(raw.get("doi"))
    arxiv_orig, arxiv_canon = nz.normalize_arxiv(raw.get("arxiv_id"))
    title = raw.get("title")
    title_norm = nz.normalize_title(title)
    key = nz.paper_key(doi, arxiv_canon, title_norm)
    label, score, reason = rel.classify(title or "", raw.get("abstract"))
    now = _now()
    return {
        "paper_key": key,
        "doi": doi,
        "arxiv_id": arxiv_orig,
        "arxiv_canonical": arxiv_canon,
        "openalex_id": raw.get("openalex_id"),
        "title": title,
        "title_norm": title_norm,
        "year": raw.get("year"),
        "authors_json": json.dumps(raw.get("authors") or [], ensure_ascii=False),
        "venue": raw.get("venue"),
        "work_type": raw.get("work_type"),
        "abstract": raw.get("abstract"),
        "cited_by_count": raw.get("cited_by_count"),
        "is_oa": 1 if raw.get("is_oa") else (0 if raw.get("is_oa") is False else None),
        "oa_url": raw.get("oa_url"),
        "relevance": label,
        "relevance_score": score,
        "matched_rq": rq,
        "discovered_by": raw.get("source"),
        "discovery_query": query,
        "status_group": "skipped" if label == "noise" else "pending",
        "reason_code": "out_of_scope" if label == "noise" else "metadata_only",
        "created_at": now,
        "updated_at": now,
    }


def cmd_discover(cfg: dict, config_hash: str, root: Path):
    """발견 파이프라인 본체."""
    disc = cfg["discovery"]
    lim = cfg["limits"]
    ident = cfg["identity"]
    mailto = ident["contact_email"]
    ua = ident["user_agent"]
    sources = disc["sources"]
    per_q = disc["per_query_limit"]
    from_year = disc["openalex_from_year"]
    max_cand = disc["max_candidates"]

    state_dir = root / cfg["output"]["state_dir"]
    conn = dbmod.connect(state_dir / "literature.db")
    run_id = _run_id()
    dbmod.start_run(conn, run_id, cfg["project"]["project_id"], config_hash,
                    "metadata_only", platform.platform(),
                    platform.python_version(), _now())

    queries = generate_queries()
    print(f"[run {run_id}] {len(queries)} queries x {len(sources)} sources")

    total_new = 0
    total_seen = 0
    for qi, q in enumerate(queries, 1):
        query, rq = q["q"], q["rq"]
        # cap은 중복 재조회가 아니라 고유(신규) 논문 수 기준으로 판단한다.
        if total_new >= max_cand:
            print(f"  max_candidates {max_cand} (unique) 도달 — 발견 중단")
            break
        for src in sources:
            try:
                status, records = _call_source(
                    src, query, from_year, per_q, mailto, ua, lim)
            except HttpError as e:
                dbmod.log_discovery(conn, {
                    "run_id": run_id, "source": src, "query": query,
                    "matched_rq": rq, "returned": 0, "new_papers": 0,
                    "http_status": e.status, "error": str(e), "ts": _now()})
                print(f"  [{qi}/{len(queries)}] {src} '{query[:40]}' ERR {e}")
                continue

            new_here = 0
            for raw in records:
                if not raw.get("title"):
                    continue
                recd = _to_record(raw, query, rq)
                is_new = dbmod.upsert_paper(conn, recd)
                total_seen += 1
                if is_new:
                    new_here += 1
                    total_new += 1
            conn.commit()
            dbmod.log_discovery(conn, {
                "run_id": run_id, "source": src, "query": query,
                "matched_rq": rq, "returned": len(records),
                "new_papers": new_here, "http_status": status,
                "error": None, "ts": _now()})
            print(f"  [{qi}/{len(queries)}] {src:9s} '{query[:38]}' "
                  f"-> {len(records):3d} ret, {new_here:3d} new")
            # polite 간격.
            time.sleep(lim["arxiv_sleep_seconds"] if src == "arxiv"
                       else lim["per_source_sleep_seconds"])

    # 리포트 생성.
    manifest = state_dir / "manifests" / "manifest.csv"
    n = rep.write_manifest(conn, cfg["project"]["project_id"], manifest)
    stats = rep.write_reports(conn, cfg, run_id,
                              root / cfg["output"]["report_dir"])
    dbmod.finish_run(conn, run_id, _now(), json.dumps(stats, ensure_ascii=False))
    conn.close()

    print(f"\n[done] unique papers={n}, new this run={total_new}")
    print(f"  relevance={stats['relevance']}")
    print(f"  manifest: {manifest}")
    print(f"  reports:  {root / cfg['output']['report_dir']}")
    return run_id


def _call_source(src, query, from_year, per_q, mailto, ua, lim):
    """소스 이름에 맞는 어댑터를 호출한다."""
    if src == "openalex":
        return openalex.search(query, from_year, per_q, mailto, ua,
                               lim["request_timeout_seconds"],
                               lim["retry_max"], lim["backoff_base_seconds"])
    if src == "arxiv":
        return arxiv.search(query, per_q, ua,
                            lim["request_timeout_seconds"],
                            lim["retry_max"], lim["backoff_base_seconds"])
    if src == "crossref":
        return crossref.search(query, from_year, per_q, mailto, ua,
                               lim["request_timeout_seconds"],
                               lim["retry_max"], lim["backoff_base_seconds"])
    raise ValueError(f"unknown source: {src}")


def _slug(title: str, n: int = 60) -> str:
    """제목을 안전한 ASCII 파일명 조각으로."""
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "_", (title or "paper")).strip("_")
    return s[:n] or "paper"


def cmd_download(cfg: dict, root: Path, tiers: list[int]):
    """on_target_tier가 지정 tier인 논문의 OA PDF를 받는다(scope B).

    OA 후보(arXiv 직접·Unpaywall)만 시도하고, 전부 실패하면
    manual_required로 남긴다. 성공분은 재실행 시 건너뛴다(멱등).
    """
    import hashlib
    state_dir = root / cfg["output"]["state_dir"]
    conn = dbmod.connect(state_dir / "literature.db")
    # 다운로드 결과 컬럼 보장.
    for col, typ in [("local_pdf_path", "TEXT"), ("content_sha256", "TEXT"),
                     ("page_count", "INTEGER"), ("validation_passed", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {col} {typ}")
        except Exception:
            pass
    conn.commit()

    ident = cfg["identity"]
    email, ua = ident["contact_email"], ident["user_agent"]
    timeout = cfg["limits"]["request_timeout_seconds"]
    pdf_dir = root / "papers" / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    ph = ",".join("?" * len(tiers))
    rows = conn.execute(
        f"""SELECT paper_key, doi, arxiv_id, title, year, status_group,
                   local_pdf_path FROM papers
            WHERE on_target_tier IN ({ph})
            ORDER BY on_target_tier""", tiers).fetchall()
    print(f"tiers {tiers}: {len(rows)} target papers")

    ok = manual = failed = skipped = 0
    manual_list = []
    for r in rows:
        key = r["paper_key"]
        # 이미 받은 유효 파일 있으면 skip(멱등).
        if r["local_pdf_path"] and Path(r["local_pdf_path"]).exists():
            skipped += 1
            print(f"  SKIP  {r['title'][:50]} (이미 있음)")
            continue
        paper = {"doi": r["doi"], "arxiv_id": r["arxiv_id"]}
        cands = resolvemod.candidates(paper, email, ua, timeout)
        fname = f"{r['year'] or 'NA'}_{_slug(r['title'])}_" \
                f"{hashlib.sha1(key.encode()).hexdigest()[:8]}.pdf"
        dest = pdf_dir / fname
        got = None
        for url, note in cands:
            if not url:
                continue
            # 후보당 최대 2회 — arXiv가 첫 히트에 HTML interstitial 주는
            # flaky 케이스를 짧은 대기 후 재시도로 흡수한다.
            for attempt in range(2):
                res = dlmod.fetch(url, dest, ua, timeout,
                                  cfg["limits"].get("max_pdf_mb", 250))
                if res["ok"]:
                    break
                time.sleep(3.0)
            if res["ok"]:
                got = (url, note, res)
                break
        now = _now()
        if got:
            url, note, res = got
            conn.execute(
                """UPDATE papers SET status_group='ok',
                       reason_code='downloaded', local_pdf_path=?,
                       content_sha256=?, page_count=?, validation_passed=1,
                       updated_at=? WHERE paper_key=?""",
                (str(dest), res["sha256"], res["page_count"], now, key))
            ok += 1
            print(f"  OK    [{note}] {r['title'][:50]} "
                  f"({res['page_count']}p)")
        else:
            conn.execute(
                """UPDATE papers SET status_group='manual_required',
                       reason_code='no_oa_or_failed', updated_at=?
                   WHERE paper_key=?""", (now, key))
            manual += 1
            manual_list.append((r["title"], r["doi"] or r["arxiv_id"],
                                [(u, n) for u, n in cands if u]))
            print(f"  MANUAL {r['title'][:50]} (OA 후보 실패: "
                  f"{[n for _,n in cands]})")
        conn.commit()
        # arXiv 등 호스트 throttle 방지 polite 간격.
        time.sleep(2.0)

    # manual queue 리포트.
    if manual_list:
        rp = root / cfg["output"]["report_dir"] / "manual_queue_targets.md"
        lines = ["# Manual Queue — TIER 다운로드 실패분", "",
                 "OA 확정이나 봇차단 등으로 HTTP 자동수집 실패. 아래 링크에서 직접 받기.", ""]
        for title, ident_, urls in manual_list:
            lines.append(f"- **{title}** `{ident_}`")
            for u, n in urls:
                lines.append(f"  - [{n}] {u}")
        rp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  manual queue -> {rp}")

    conn.close()
    print(f"\n[download done] ok={ok}, manual={manual}, "
          f"skipped={skipped}, total={len(rows)}")
    print(f"  pdfs: {pdf_dir}")


def cmd_report(cfg: dict, root: Path):
    """DB에서 리포트만 재생성한다."""
    state_dir = root / cfg["output"]["state_dir"]
    conn = dbmod.connect(state_dir / "literature.db")
    n = rep.write_manifest(conn, cfg["project"]["project_id"],
                           state_dir / "manifests" / "manifest.csv")
    stats = rep.write_reports(conn, cfg, "latest",
                              root / cfg["output"]["report_dir"])
    conn.close()
    print(f"[report] papers={n}, relevance={stats['relevance']}")


def main(argv=None):
    """CLI 파서."""
    ap = argparse.ArgumentParser(description="literature discovery (scope A)")
    ap.add_argument("command", choices=["discover", "report", "download"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--tiers", default="1,2",
                    help="download 대상 on_target_tier (예: 1,2)")
    args = ap.parse_args(argv)

    cfg, config_hash = cfgmod.load_config(args.config)
    root = cfgmod.project_root(cfg)
    if args.command == "discover":
        cmd_discover(cfg, config_hash, root)
    elif args.command == "download":
        tiers = [int(x) for x in args.tiers.split(",") if x.strip()]
        cmd_download(cfg, root, tiers)
    else:
        cmd_report(cfg, root)


if __name__ == "__main__":
    main()
