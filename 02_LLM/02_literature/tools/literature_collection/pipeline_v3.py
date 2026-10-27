"""OA-only, resumable literature collector for GenAI traffic fingerprinting."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, platform, re, sqlite3, sys, time, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, urlparse

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
import requests
import yaml
from pypdf import PdfReader

QUERIES = [
    ("LLM chatbot encrypted traffic fingerprinting", "RQ1,RQ2"),
    ("ChatGPT Claude Gemini traffic classification", "RQ2"),
    ("generative AI service network traffic identification", "RQ1,RQ2"),
    ("voice chat WebRTC traffic classification timing", "RQ3"),
    ("real time voice assistant encrypted traffic analysis", "RQ3"),
    ("server sent events token streaming traffic timing", "RQ3,RQ4"),
    ("LLM output token count timing side channel", "RQ4,RQ5"),
    ("extended thinking language model inference latency", "RQ4,RQ5"),
    ("remote timing attacks efficient language model inference", "RQ4,RQ5"),
    ("encrypted traffic application fingerprinting SNI free", "RQ2"),
    ("website fingerprinting encrypted traffic deep learning", "RQ2"),
    ("open world encrypted traffic classification OOD", "RQ6"),
    ("encrypted traffic classification concept drift generalization", "RQ6"),
    ("hierarchical multi task encrypted traffic classification", "RQ1,RQ6"),
    # --- 작업단계·에이전트 행동 추론 축 (핵심 신규, 2026-09-01 추가) ---
    ("LLM agent network traffic identification tool use", "RQ4,RQ5"),
    ("autonomous agent versus human traffic classification", "RQ5"),
    ("bot human behavior network traffic distinction", "RQ5"),
    ("coding assistant copilot traffic fingerprinting", "RQ2,RQ5"),
    ("task type inference encrypted traffic side channel", "RQ4"),
    ("image generation diffusion service traffic classification", "RQ3"),
    ("API automated versus interactive user traffic pattern", "RQ5"),
    ("agentic workflow tool calling traffic pattern", "RQ4,RQ5"),
]
SEEDS = [
    {"title":"Whisper Leak: a side-channel attack on Large Language Models", "arxiv_id":"2511.03675", "year":2025, "rq":"RQ4,RQ5"},
    {"title":"Time Will Tell: Timing Side Channels via Output Token Count in LLMs", "arxiv_id":"2412.15431", "year":2024, "rq":"RQ4,RQ5"},
    {"title":"Remote Timing Attacks on Efficient Language Model Inference", "arxiv_id":"2410.17175", "year":2024, "rq":"RQ4,RQ5"},
    {"title":"Hello, GenAI? Dissecting Human to Generative AI Calling", "doi":"10.1145/3730567.3764441", "year":2025, "rq":"RQ1,RQ2,RQ3"},
]
TRAFFIC = ("traffic", "packet", "flow", "encrypted", "tls", "quic", "websocket", "webrtc", "sse", "server-sent", "fingerprint", "side channel", "side-channel")
TARGET = ("chatgpt", "claude", "gemini", "chatbot", "generative ai", "large language model", "llm", "language model", "voice assistant", "token streaming", "extended thinking", "reasoning")
METHOD = ("classification", "fingerprint", "identification", "representation", "transformer", "deep learning", "open world", "out-of-distribution", "concept drift", "generalization", "dataset", "benchmark", "webrtc", "quic")
EXCLUDE = ("intrusion detection", "malware", "anomaly detection", "synthetic traffic", "traffic generation", "network attack detection", "sentiment", "medical", "protein")


def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def run_id(): return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
def norm_title(s): return re.sub(r"\s+", " ", (s or "").lower()).strip()
def norm_doi(s):
    if not s: return None
    s = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)\s*", "", str(s).strip(), flags=re.I).rstrip(". ,;")
    return s.lower() if s.startswith("10.") else None
def norm_arxiv(s):
    if not s: return None
    s = re.sub(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv[:.])", "", str(s).strip(), flags=re.I)
    return re.sub(r"v\d+$", "", s)
def paper_key(doi, arxiv_id, title):
    if doi: return "doi:" + doi
    if arxiv_id: return "arxiv:" + arxiv_id
    return "title:" + hashlib.sha256(norm_title(title).encode()).hexdigest()[:20]
def slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "_", s or "paper").strip("_")
    return (s[:105] or "paper")
def read_cfg(path):
    with open(path, encoding="utf-8") as f: return yaml.safe_load(f)
def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

def classify(title, abstract=None, force_seed=False):
    text = (title or "").lower()
    traffic = any(x in text for x in TRAFFIC)
    target = any(x in text for x in TARGET)
    method = any(x in text for x in METHOD)
    excluded = any(x in text for x in EXCLUDE)
    timing_target = target and any(x in text for x in ("timing", "latency", "inference", "reasoning", "side channel", "side-channel", "token count"))
    if force_seed: return "core", 1.0, "configured_seed"
    if excluded and not ("side channel" in text or "side-channel" in text):
        return "noise", 0.0, "excluded_tool_or_domain"
    if traffic and target:
        return "core", 0.92, "title_has_traffic_and_genai_target"
    if traffic and method:
        return "method", 0.72, "title_has_traffic_methodology"
    if timing_target:
        return "method", 0.66, "title_has_llm_timing_methodology"
    if traffic:
        return "background", 0.40, "title_has_traffic_background"
    return "noise", 0.0, "out_of_scope"
def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path)); c.row_factory = sqlite3.Row
    c.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS papers (
      paper_key TEXT PRIMARY KEY, doi TEXT, arxiv_id TEXT, title TEXT NOT NULL, title_norm TEXT,
      year INTEGER, authors_json TEXT, venue TEXT, work_type TEXT, abstract TEXT,
      relevance TEXT, relevance_score REAL, category TEXT, discovered_by TEXT, discovery_query TEXT,
      matched_rq TEXT, status_group TEXT, reason_code TEXT, next_action TEXT,
      local_pdf_path TEXT, content_sha256 TEXT, page_count INTEGER, title_similarity REAL,
      validation_passed INTEGER DEFAULT 0, access_route TEXT, source_url TEXT, resolved_url TEXT,
      oa_version TEXT, license TEXT, attempt_count INTEGER DEFAULT 0, http_status INTEGER,
      content_type TEXT, file_name TEXT, size_bytes INTEGER, retrieved_at TEXT, last_error TEXT,
      created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS locations (
      paper_key TEXT, source TEXT, url TEXT, host TEXT, version TEXT, is_oa INTEGER, license TEXT,
      priority INTEGER, discovered_at TEXT, UNIQUE(paper_key,url));
    CREATE TABLE IF NOT EXISTS attempts (
      run_id TEXT, paper_key TEXT, stage TEXT, adapter TEXT, url TEXT, started_at TEXT, ended_at TEXT,
      http_status INTEGER, content_type TEXT, outcome TEXT, error_class TEXT, error_message TEXT);
    CREATE TABLE IF NOT EXISTS runs (
      run_id TEXT PRIMARY KEY, project_id TEXT, config_hash TEXT, os TEXT, python_version TEXT,
      started_at TEXT, ended_at TEXT, status TEXT, stats_json TEXT);
    CREATE TABLE IF NOT EXISTS query_log (
      run_id TEXT, source TEXT, query TEXT, matched_rq TEXT, returned INTEGER, new_papers INTEGER,
      http_status INTEGER, error TEXT, ts TEXT);
    """)
    return c

def ensure_dirs(root, cfg):
    for rel in [cfg["output"]["pdf_dir"], cfg["output"]["state_dir"], cfg["output"]["report_dir"],
                cfg["output"]["manifest_dir"], cfg["output"]["raw_api_dir"], cfg["output"]["quarantine_dir"],
                cfg["input"]["manual_import_dir"]]:
        (root / rel).mkdir(parents=True, exist_ok=True)

def valid_pdf(path):
    try:
        if path.stat().st_size < 1024: return False, "too_small", None, 0, ""
        with open(path, "rb") as f:
            if not f.read(5).startswith(b"%PDF-"): return False, "invalid_magic", None, 0, ""
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        reader = PdfReader(str(path))
        pages = len(reader.pages)
        text = "".join((reader.pages[i].extract_text() or "") for i in range(min(pages, 2)))
        return pages >= 1, "valid" if pages >= 1 else "no_pages", sha, pages, text
    except Exception as e:
        return False, "pdf_parse_error:" + type(e).__name__, None, 0, ""

def title_similarity(expected, text):
    actual = norm_title(text[:3000])
    if not actual: return 0.0
    return round(SequenceMatcher(None, norm_title(expected), actual).ratio(), 3)

def config_hash(cfg): return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]
def upsert_paper(c, r):
    old = c.execute("SELECT * FROM papers WHERE paper_key=?", (r["paper_key"],)).fetchone()
    if old:
        c.execute("UPDATE papers SET abstract=COALESCE(abstract,?), oa_version=COALESCE(oa_version,?), source_url=COALESCE(source_url,?), discovered_by=?, discovery_query=?, matched_rq=?, relevance=?, relevance_score=?, updated_at=? WHERE paper_key=?", (r.get("abstract"),r.get("oa_version"),r.get("source_url"),r.get("discovered_by"),r.get("discovery_query"),r.get("matched_rq"),r.get("relevance"),r.get("relevance_score"),now(),r["paper_key"]))
        return False
    cols = list(r); c.execute("INSERT INTO papers (%s) VALUES (%s)" % (",".join(cols), ",".join("?"*len(cols))), [r[x] for x in cols]); return True

def record(c, raw, source, query, rq, force_seed=False):
    doi, aid = norm_doi(raw.get("doi")), norm_arxiv(raw.get("arxiv_id"))
    title = raw.get("title") or ""
    rel, score, why = classify(title, raw.get("abstract"), force_seed)
    key = paper_key(doi, aid, title)
    r = {"paper_key":key,"doi":doi,"arxiv_id":aid,"title":title,"title_norm":norm_title(title),"year":raw.get("year"),"authors_json":json.dumps(raw.get("authors") or [],ensure_ascii=False),"venue":raw.get("venue"),"work_type":raw.get("work_type"),"abstract":raw.get("abstract"),"relevance":rel,"relevance_score":score,"category":why,"discovered_by":source,"discovery_query":query,"matched_rq":rq,"status_group":"skipped" if rel=="noise" else "pending","reason_code":"out_of_scope" if rel=="noise" else "metadata_discovered","next_action":"none" if rel=="noise" else "resolve_oa","local_pdf_path":None,"content_sha256":None,"page_count":None,"title_similarity":None,"validation_passed":0,"access_route":None,"source_url":raw.get("oa_url"),"resolved_url":None,"oa_version":raw.get("oa_version"),"license":raw.get("license"),"attempt_count":0,"http_status":None,"content_type":None,"file_name":None,"size_bytes":None,"retrieved_at":None,"last_error":None,"created_at":now(),"updated_at":now()}
    new = upsert_paper(c,r)
    if raw.get("oa_url"): add_location(c,key,"openalex",raw["oa_url"],raw.get("oa_version") or "unknown",True,raw.get("license"),70)
    return new

def add_location(c,key,source,url,version,is_oa,license_,priority):
    if not url: return
    c.execute("INSERT OR IGNORE INTO locations VALUES (?,?,?,?,?,?,?,?,?)",(key,source,url,urlparse(url).netloc,version,1 if is_oa else 0,license_,priority,now()))

def get_json(session,url,params,headers,timeout):
    for n in range(3):
        try:
            resp=session.get(url,params=params,headers=headers,timeout=(10,timeout))
            if resp.status_code==200: return resp,resp.json()
            if resp.status_code not in (429,500,502,503,504): return resp,None
        except requests.RequestException: resp=None
        time.sleep(min(2**n,8))
    return resp,None

def discover(cfg,root,c,rid):
    rawdir=root/cfg["output"]["raw_api_dir"]/rid; rawdir.mkdir(parents=True,exist_ok=True)
    session=requests.Session(); headers={"User-Agent":cfg["identity"]["user_agent"]}; email=os.getenv(cfg["identity"]["contact_email_env"]) or cfg["identity"]["contact_email"]
    new=0
    for seed in SEEDS: new += record(c,seed,"seed","configured_seed",seed["rq"],True)
    c.commit()
    for ix,(query,rq) in enumerate(QUERIES,1):
        resp,data=get_json(session,"https://api.openalex.org/works",{"search":query,"filter":"from_publication_date:%s-01-01"%cfg["discovery"]["openalex_from_year"],"per-page":cfg["discovery"]["per_query_limit"]},headers,cfg["limits"]["request_timeout_seconds"])
        status=resp.status_code if resp else 0; write_json(rawdir/("openalex_%02d.json"%ix),data or {"error":status})
        add=0
        for w in (data or {}).get("results",[]):
            loc=w.get("best_oa_location") or {}; aid=None
            for x in w.get("locations") or []:
                lp=x.get("landing_page_url") or ""
                if "arxiv.org" in lp: aid=lp.rsplit("/",1)[-1]; break
            inv=w.get("abstract_inverted_index") or {}; abstract=" ".join(k for k,_ in sorted(((word,p) for word,ps in inv.items() for p in ps),key=lambda z:z[1])) if inv else None
            add += record(c,{"doi":w.get("doi"),"arxiv_id":aid,"title":w.get("display_name"),"year":w.get("publication_year"),"authors":[(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []],"venue":((w.get("primary_location") or {}).get("source") or {}).get("display_name"),"work_type":w.get("type"),"abstract":abstract,"oa_url":loc.get("pdf_url") or loc.get("landing_page_url"),"oa_version":loc.get("version"),"license":loc.get("license")},"openalex",query,rq)
        c.execute("INSERT INTO query_log VALUES (?,?,?,?,?,?,?, ?,?)",(rid,"openalex",query,rq,len((data or {}).get("results",[])),add,status,None if data else "http_error",now())); c.commit(); new += add
        time.sleep(cfg["limits"]["per_source_sleep_seconds"])
    return new

def resolve(c,cfg,rid):
    email=os.getenv(cfg["identity"]["contact_email_env"]) or cfg["identity"]["contact_email"]; headers={"User-Agent":cfg["identity"]["user_agent"]}; session=requests.Session()
    rows=c.execute("SELECT paper_key,doi,arxiv_id,source_url FROM papers WHERE relevance IN ('core','method') AND status_group='pending'").fetchall()
    for r in rows:
        key=r["paper_key"]
        if r["arxiv_id"]: add_location(c,key,"arxiv","https://arxiv.org/pdf/"+r["arxiv_id"],"submitted",True,None,90)
        if r["doi"] and not r["doi"].startswith("10.48550/arxiv."):
            resp,data=get_json(session,"https://api.unpaywall.org/v2/"+quote(r["doi"],safe=""),{"email":email},headers,cfg["limits"]["request_timeout_seconds"])
            for loc in ([((data or {}).get("best_oa_location"))] + ((data or {}).get("oa_locations") or [])):
                if loc:
                    add_location(c,key,"unpaywall",loc.get("url_for_pdf") or loc.get("url"),loc.get("version") or "unknown",True,loc.get("license"),100 if loc.get("version")=="publishedVersion" else 80)
            c.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(rid,key,"resolve","unpaywall",r["doi"],now(),now(),resp.status_code if resp else 0,"application/json","ok" if data else "failed",None,None if data else "unpaywall_unavailable"))
        have=c.execute("SELECT COUNT(*) FROM locations WHERE paper_key=? AND is_oa=1",(key,)).fetchone()[0]
        if not have: c.execute("UPDATE papers SET status_group='no_oa',reason_code='no_legal_oa_location',next_action='manual_metadata_review',updated_at=? WHERE paper_key=?",(now(),key))
        c.commit()

def acquire_one(c,cfg,root,rid,row):
    key=row["paper_key"]; threshold=cfg["collection_policy"]["min_title_similarity"]; pdir=root/cfg["output"]["pdf_dir"]; qdir=root/cfg["output"]["quarantine_dir"]
    existing=row["local_pdf_path"]
    if row["status_group"]=="ok" and existing and Path(existing).exists():
        ok,_,sha,pages,_=valid_pdf(Path(existing))
        if ok and sha==row["content_sha256"]: return "skip"
    locs=c.execute("SELECT * FROM locations WHERE paper_key=? AND is_oa=1 ORDER BY priority DESC",(key,)).fetchall()
    if not locs: return "no_oa"
    ua=cfg["identity"]["user_agent"]; session=requests.Session(); last=""
    for loc in locs:
        url=loc["url"]; start=now(); status=0; ctype=""
        name=(str(row["year"] or "NA")+"_"+slug(row["title"])+"_"+hashlib.sha1(key.encode()).hexdigest()[:8]+".pdf")
        dest=pdir/name; part=dest.with_suffix(".part")
        try:
            with session.get(url,headers={"User-Agent":ua,"Accept":"application/pdf,*/*"},timeout=(10,cfg["limits"]["request_timeout_seconds"]),stream=True,allow_redirects=True) as resp:
                status=resp.status_code; ctype=resp.headers.get("Content-Type","")
                if status==200:
                    total=0; limit=cfg["limits"]["max_pdf_mb"]*1024*1024
                    with open(part,"wb") as f:
                        for chunk in resp.iter_content(65536):
                            total += len(chunk)
                            if total>limit: raise ValueError("oversized_manual")
                            f.write(chunk)
                    ok,why,sha,pages,text=valid_pdf(part); sim=title_similarity(row["title"],text)
                    exact=(row["doi"] and row["doi"].lower() in text.lower()) or (row["arxiv_id"] and row["arxiv_id"] in text)
                    if ok and (sim>=threshold or exact):
                        part.replace(dest); c.execute("UPDATE papers SET status_group='ok',reason_code=?,next_action='none',local_pdf_path=?,content_sha256=?,page_count=?,title_similarity=?,validation_passed=1,access_route=?,source_url=?,resolved_url=?,oa_version=?,license=?,attempt_count=attempt_count+1,http_status=?,content_type=?,file_name=?,size_bytes=?,retrieved_at=?,last_error=NULL,updated_at=? WHERE paper_key=?",("downloaded_"+loc["source"],str(dest),sha,pages,sim,loc["source"],url,resp.url,loc["version"],loc["license"],status,ctype,name,total,now(),now(),key)); c.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(rid,key,"download",loc["source"],url,start,now(),status,ctype,"ok",None,None)); c.commit(); return "ok"
                    qdir.mkdir(parents=True,exist_ok=True); bad=qdir/(name+".title_mismatch")
                    part.replace(bad); last=why if not ok else "title_mismatch"
                else: last="http_%s"%status
        except Exception as e:
            last=type(e).__name__ if not last else last
        finally:
            if part.exists(): part.unlink()
        c.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(rid,key,"download",loc["source"],url,start,now(),status,ctype,"failed",last,last)); c.commit()
    c.execute("UPDATE papers SET status_group='failed',reason_code=?,next_action='browser_oa_retry_or_manual_download',attempt_count=attempt_count+1,last_error=?,updated_at=? WHERE paper_key=?",(last,last,now(),key)); c.commit(); return "failed"

def acquire(c,cfg,root,rid,canary=False):
    lim=5 if canary else cfg["limits"]["max_download_candidates"]
    rows=c.execute("SELECT * FROM papers WHERE relevance IN ('core','method') AND status_group IN ('pending','failed') ORDER BY CASE relevance WHEN 'core' THEN 0 ELSE 1 END, relevance_score DESC, year DESC LIMIT ?",(lim,)).fetchall()
    outcomes={}
    for row in rows:
        got=acquire_one(c,cfg,root,rid,row); outcomes[got]=outcomes.get(got,0)+1; time.sleep(0.35)
    return outcomes

def preflight(cfg,root,c,rid):
    ensure_dirs(root,cfg); sdir=root/cfg["output"]["state_dir"]; pdfs=list((root/cfg["output"]["pdf_dir"]).glob("*.pdf")); valid=0
    unmatched=[]
    for p in pdfs:
        ok,_,_,_,_=valid_pdf(p); valid += int(ok)
        if not c.execute("SELECT 1 FROM papers WHERE local_pdf_path=?",(str(p),)).fetchone(): unmatched.append(str(p))
    info={"run_id":rid,"project":cfg["project"]["project_id"],"root":str(root),"os":platform.platform(),"python":sys.version,"metadata_records":c.execute("SELECT COUNT(*) FROM papers").fetchone()[0],"existing_pdf_files":len(pdfs),"existing_valid_pdfs":valid,"unmatched_existing_pdfs":unmatched,"api_env_present":{k:bool(os.getenv(k)) for k in ["LIT_CONTACT_EMAIL","UNPAYWALL_EMAIL","OPENALEX_API_KEY","S2_API_KEY","CROSSREF_MAILTO"]},"institutional_access_authorized":cfg["access"]["institutional_access_authorized"]}
    write_json(sdir/"runs"/rid/"preflight.json",info); return info

def write_reports(c,cfg,root,rid):
    state=root/cfg["output"]["state_dir"]; reports=root/cfg["output"]["report_dir"]; mdir=state/"manifests"; rows=c.execute("SELECT * FROM papers ORDER BY relevance_score DESC,title").fetchall()
    cols=["project_id","paper_key","doi","arxiv_id","pmcid","title","year","work_type","relevance","status_group","reason_code","next_action","access_route","source_adapter","source_url","resolved_url","oa_version","license","attempt_count","http_status","content_type","file","local_pdf_path","sha256","size_bytes","page_count","title_similarity","validation_passed","retrieved_at","last_error","run_id"]
    def writecsv(path,subset):
        tmp=path.with_suffix(".tmp"); path.parent.mkdir(parents=True,exist_ok=True)
        with open(tmp,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
            for x in subset: w.writerow({"project_id":cfg["project"]["project_id"],"paper_key":x["paper_key"],"doi":x["doi"],"arxiv_id":x["arxiv_id"],"pmcid":"","title":x["title"],"year":x["year"],"work_type":x["work_type"],"relevance":x["relevance"],"status_group":x["status_group"],"reason_code":x["reason_code"],"next_action":x["next_action"],"access_route":x["access_route"],"source_adapter":x["discovered_by"],"source_url":x["source_url"],"resolved_url":x["resolved_url"],"oa_version":x["oa_version"],"license":x["license"],"attempt_count":x["attempt_count"],"http_status":x["http_status"],"content_type":x["content_type"],"file":x["file_name"],"local_pdf_path":x["local_pdf_path"],"sha256":x["content_sha256"],"size_bytes":x["size_bytes"],"page_count":x["page_count"],"title_similarity":x["title_similarity"],"validation_passed":x["validation_passed"],"retrieved_at":x["retrieved_at"],"last_error":x["last_error"],"run_id":rid})
        tmp.replace(path)
    writecsv(mdir/"manifest.csv",rows)
    mapping={"collected.csv":"ok","no_oa.csv":"no_oa","failed.csv":"failed","not_found.csv":"not_found","manual_required.csv":"manual_required","junk_nonpaper.csv":"skipped"}
    for f,status in mapping.items(): writecsv(mdir/f,[x for x in rows if x["status_group"]==status])
    sc=dict(c.execute("SELECT status_group,COUNT(*) FROM papers GROUP BY status_group").fetchall()); rel=dict(c.execute("SELECT relevance,COUNT(*) FROM papers GROUP BY relevance").fetchall()); sources=c.execute("SELECT COALESCE(access_route,'unacquired'),status_group,COUNT(*) FROM papers GROUP BY access_route,status_group").fetchall(); oks=[x for x in rows if x["status_group"]=="ok"]; bytes_=sum(x["size_bytes"] or 0 for x in oks)
    report=["# Literature Collection Report","",f"- Project: {cfg['project']['project_id']}",f"- Run ID: `{rid}`",f"- Input unique papers: {len(rows)}",f"- Existing valid PDFs: {len(oks)}",f"- Newly acquired PDFs: {len(oks)}",f"- Final unique PDFs: {len(oks)}",f"- Validated size: {bytes_} bytes",f"- OA success rate: {len(oks)}/{max(1,len([x for x in rows if x['relevance'] in ('core','method')]))}","- Institutional success rate: disabled (OA-only)","", "## Status","| status | count | next action |","|---|---:|---|"]
    actions={"pending":"resolve/acquire","ok":"none","no_oa":"manual metadata review","failed":"browser OA retry or manual download","not_found":"title/author/year resolution","manual_required":"manual review","skipped":"out of scope"}
    for s in ["pending","ok","no_oa","failed","not_found","manual_required","skipped"]: report.append(f"| {s} | {sc.get(s,0)} | {actions[s]} |")
    report += ["","## Source breakdown","| source/adapter | status | count |","|---|---|---:|"]+[f"| {a} | {b} | {n} |" for a,b,n in sources]
    report += ["","## Integrity audit",f"- PDF magic/parser passed: {len(oks)}",f"- Title-match validation passed: {sum(1 for x in oks if x['title_similarity'] is not None)}",f"- Duplicate content: {len(oks)-len(set(x['content_sha256'] for x in oks))}",f"- Legacy/unmatched local PDFs remain preserved: see `preflight.json`.","", "## Remaining queues",f"- no_oa: {sc.get('no_oa',0)}",f"- failed: {sc.get('failed',0)}",f"- not_found: {sc.get('not_found',0)}",f"- manual_required: {sc.get('manual_required',0)}",f"- junk_nonpaper/out_of_scope: {sc.get('skipped',0)}"]
    atomic_text(reports/f"collection_report_{rid}.md","\n".join(report)+"\n")
    cov=["# Coverage Report","",f"- Project: {cfg['project']['project_id']}",f"- Run ID: `{rid}`","", "| RQ | core/method papers |","|---|---:|"]
    for rq in range(1,7):
        n = c.execute("SELECT COUNT(*) FROM papers WHERE relevance IN ('core','method') AND matched_rq LIKE ?", (f"%RQ{rq}%",)).fetchone()[0]
        cov.append(f"| RQ{rq} | {n} |")
    atomic_text(reports/f"coverage_report_{rid}.md","\n".join(cov)+"\n")
    manual=["# Manual Queue","", "OA-only pipeline: do not bypass paywalls. Items below need an authorized human review.",""]
    for x in rows:
        if x["status_group"] in ("no_oa","failed","manual_required"): manual.append(f"- **{x['title']}** — `{x['doi'] or x['arxiv_id'] or x['paper_key']}` — {x['reason_code']} → {x['next_action']}")
    atomic_text(reports/f"manual_queue_{rid}.md","\n".join(manual)+"\n")
    return sc

def self_test():
    assert norm_doi("https://doi.org/10.1/ABC") == "10.1/abc"; assert norm_arxiv("arXiv:2201.12345v3")=="2201.12345"; assert paper_key("10.1/x",None,"a")=="doi:10.1/x"; assert classify("LLM chatbot encrypted traffic fingerprinting")[0]=="core"; assert classify("LLM intrusion detection for network traffic")[0]=="noise"; print("self-test: 5 passed")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("command",choices=["preflight","discover","resolve","canary","acquire","report","run","self-test"]); ap.add_argument("--config",required=False,default=str(HERE.parent.parent/"config"/"collection.yaml")); args=ap.parse_args()
    if args.command=="self-test": self_test(); return
    cfg=read_cfg(args.config); root=Path(cfg["project"]["root"]); ensure_dirs(root,cfg); rid=run_id(); c=connect(root/cfg["output"]["state_dir"]/'literature.db'); c.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)",(rid,cfg["project"]["project_id"],config_hash(cfg),platform.platform(),platform.python_version(),now(),None,"running",None));c.commit()
    try:
        if args.command in ("preflight","run"): preflight(cfg,root,c,rid)
        if args.command in ("discover","run"): discover(cfg,root,c,rid)
        if args.command in ("resolve","run"): resolve(c,cfg,rid)
        if args.command in ("canary","run"):
            out=acquire(c,cfg,root,rid,True); print("canary",out)
            if not out.get("ok"): raise RuntimeError("canary acquired no valid OA PDF; full acquisition stopped")
        if args.command in ("acquire","run"): print("acquire",acquire(c,cfg,root,rid,False))
        if args.command in ("report","run"): stats=write_reports(c,cfg,root,rid)
        else: stats={}
        c.execute("UPDATE runs SET ended_at=?,status='done',stats_json=? WHERE run_id=?",(now(),json.dumps(stats),rid));c.commit();print("run",rid,"done",stats)
    except Exception as e:
        c.execute("UPDATE runs SET ended_at=?,status='failed',stats_json=? WHERE run_id=?",(now(),json.dumps({"error":repr(e)}),rid));c.commit();raise
    finally: c.close()
if __name__=='__main__': main()
