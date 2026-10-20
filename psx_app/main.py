import json
import re
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from psx_app.config import APP_ROOT, AUTHORIZED_ACCOUNTS, CORE_36_TICKERS, DATA_ROOT, DB_PATH, DOCS_DIR, SKILLS_DIR
from psx_app.database.repository import Repository
from psx_app.database.schema import init_db, get_connection
from psx_app.services.account_service import AccountService
from psx_app.services.backup_service import BackupService
from psx_app.services.export_service import ExportService
from psx_app.services.futures_service import FuturesService
from psx_app.services.import_orchestrator import ImportOrchestrator
from psx_app.services.intelligence_service import IntelligenceService
from psx_app.services.migration_service import MigrationService
from psx_app.services.reconciliation_service import ReconciliationService
from psx_app.services.technical_service import TechnicalService
from psx_app.services.top5_service import Top5Service
from psx_app.services.cloud_sync_service import CloudSyncService

# Fast in-memory cache invalidated automatically on any data commit, settings update, or backup restore
_API_CACHE: Dict[str, Any] = {}


def invalidate_api_cache() -> None:
    _API_CACHE.clear()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    CloudSyncService(DB_PATH).pull_latest_db_on_startup()
    init_db(DB_PATH)
    mig = MigrationService(DB_PATH, DATA_ROOT)
    mig.run_initial_migration(force=False)
    # Pre-warm primary overview and intelligence cards for instant first load
    try:
        api_overview()
        api_trading_ideas()
        api_automated_analyst("ATRL")
    except Exception:
        pass
    yield


app = FastAPI(
    title="PSX Trading Intelligence Dashboard",
    description="Unified Local-First Pakistan Stock Exchange Trading, Futures, Volume Register & Technical Intelligence Platform",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Request Models
# ------------------------------------------------------------------
class CommitBatchRequest(BaseModel):
    batch_uuid: str
    allow_revisions: bool = True


class ChunkedUploadEntry(BaseModel):
    upload_id: str
    name: str
    total_chunks: int


class ChunkedStageRequest(BaseModel):
    uploads: List[ChunkedUploadEntry]


class UpdateSettingsRequest(BaseModel):
    updates: Dict[str, Any]
    notes: str = "Updated via Settings UI"


class CreateBackupRequest(BaseModel):
    label: str = "manual_ui"
    include_raw_archive: bool = False


class RestoreBackupRequest(BaseModel):
    zip_filename: str


# ------------------------------------------------------------------
# 1. Overview & System Status Endpoints
# ------------------------------------------------------------------
@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    b_svc = BackupService(DB_PATH, DATA_ROOT)
    return {
        "status": "ok",
        "app": "PSX Trading Intelligence Dashboard",
        "version": "1.1.0",
        "db_integrity": b_svc.run_integrity_check(),
    }


@app.get("/api/overview")
def api_overview() -> Dict[str, Any]:
    if "overview" in _API_CACHE:
        return _API_CACHE["overview"]

    repo = Repository(DB_PATH)
    acc_svc = AccountService(DB_PATH)
    top5_svc = Top5Service(DB_PATH)
    fut_svc = FuturesService(DB_PATH)
    tech_svc = TechnicalService(DB_PATH)
    intel_svc = IntelligenceService(DB_PATH)

    sys_ov = repo.get_system_overview()
    acc_91404 = acc_svc.get_account_report("91404")["dashboard"]
    acc_91269 = acc_svc.get_account_report("91269")["dashboard"]
    top5_latest = top5_svc.get_register(
        start_date=sys_ov["top5"]["max_date"],
        end_date=sys_ov["top5"]["max_date"],
    )
    fut_latest = fut_svc.get_comparison_rows("monthly_comparison", days=30)
    tech_core = tech_svc.get_universe_summary(scope="core36")
    ideas_preview = intel_svc.generate_trading_ideas(scope_or_sector="CORE36", limit=5)

    res = {
        "system": sys_ov,
        "account_91404": acc_91404,
        "account_91269": acc_91269,
        "top5_latest_date": sys_ov["top5"]["max_date"],
        "top5_latest_blocks": top5_latest["date_blocks"][:8],
        "futures_highlights": {
            "selected_date": fut_latest["selected_date"],
            "contracts_compared": fut_latest["rows_count"],
            "lowest_annualized": fut_latest["rows"][:5],
            "highest_annualized": list(reversed(fut_latest["rows"][-5:])) if fut_latest["rows"] else [],
        },
        "technical_core36": {
            "count": tech_core["count"],
            "signal_counts": tech_core["signal_counts"],
            "top_bullish": sorted(tech_core["items"], key=lambda x: x["signal"]["score"], reverse=True)[:6],
            "top_bearish": sorted(tech_core["items"], key=lambda x: x["signal"]["score"])[:6],
        },
        "trading_ideas_default": ideas_preview,
    }
    _API_CACHE["overview"] = res
    return res


# ------------------------------------------------------------------
# New Intelligence Cards Endpoints (Trading Ideas Generator & Automated Technical Analyst)
# ------------------------------------------------------------------
@app.get("/api/intelligence/filters")
def api_intelligence_filters() -> Dict[str, Any]:
    svc = IntelligenceService(DB_PATH)
    return svc.get_available_sectors_and_filters()


@app.get("/api/intelligence/trading-ideas")
def api_trading_ideas(
    scope_or_sector: str = Query("CORE36"),
    direction: str = Query("ALL"),
    query: str = Query(""),
    limit: int = Query(5),
) -> Dict[str, Any]:
    cache_key = f"ideas:{scope_or_sector}:{direction}:{query}:{limit}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = IntelligenceService(DB_PATH)
    res = svc.generate_trading_ideas(
        scope_or_sector=scope_or_sector,
        direction_filter=direction,
        custom_query=query,
        limit=limit,
    )
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/intelligence/automated-analyst/{symbol}")
def api_automated_analyst(
    symbol: str,
    action: str = Query("Evaluate Buy / Hold / Sell"),
) -> Dict[str, Any]:
    cache_key = f"analyst:{symbol.upper()}:{action}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = IntelligenceService(DB_PATH)
    res = svc.run_automated_technical_analyst(symbol=symbol, intended_action=action)
    _API_CACHE[cache_key] = res
    return res


# ------------------------------------------------------------------
# 2. Import & Update Center Endpoints
# ------------------------------------------------------------------
@app.post("/api/imports/stage")
async def api_stage_imports(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    payload = []
    for f in files:
        content = await f.read()
        payload.append((f.filename or "upload.txt", content))
    orch = ImportOrchestrator(DB_PATH, DATA_ROOT)
    return orch.stage_uploaded_files(payload, source_label="Manual UI Upload")


# ------------------------------------------------------------------
# Chunked upload (bypasses Vercel's ~4.5 MB per-request body limit):
# the browser slices large files into small pieces that are written to a
# temporary chunk directory, then reassembled and staged server-side.
# ------------------------------------------------------------------
_CHUNK_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{8,80}$")
_MAX_CHUNK_BYTES = 4 * 1024 * 1024  # individual chunk must stay under the platform body limit
_MAX_ASSEMBLED_BYTES = 512 * 1024 * 1024


def _chunk_dir(upload_id: str) -> Path:
    return DATA_ROOT / "data" / "staging" / "_chunks" / upload_id


def _sweep_stale_chunks(max_age_seconds: int = 3 * 3600) -> None:
    base = DATA_ROOT / "data" / "staging" / "_chunks"
    if not base.exists():
        return
    now = datetime.now(timezone.utc).timestamp()
    for d in base.iterdir():
        try:
            if d.is_dir() and now - d.stat().st_mtime > max_age_seconds:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


@app.post("/api/imports/upload-chunk")
async def api_upload_chunk(request: Request) -> Dict[str, Any]:
    upload_id = (request.query_params.get("upload_id") or "").strip()
    name = Path(request.query_params.get("name") or "").name
    try:
        idx = int(request.query_params.get("idx", "-1"))
        total = int(request.query_params.get("total", "0"))
    except ValueError:
        raise HTTPException(status_code=400, detail="idx/total must be integers.")
    if not _CHUNK_ID_RE.match(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload_id.")
    if not name:
        raise HTTPException(status_code=400, detail="Missing file name.")
    if total < 1 or total > 2000 or idx < 0 or idx >= total:
        raise HTTPException(status_code=400, detail="Invalid chunk coordinates (idx/total).")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty chunk body.")
    if len(body) > _MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail=f"Chunk exceeds {_MAX_CHUNK_BYTES} bytes; the browser should slice smaller.")
    d = _chunk_dir(upload_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{idx:06d}.part").write_bytes(body)
    meta = {"name": name, "total": total, "updated_at": datetime.now(timezone.utc).isoformat()}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {"stored": True, "idx": idx, "total": total, "name": name}


@app.post("/api/imports/stage-chunked")
def api_stage_chunked(req: ChunkedStageRequest) -> Dict[str, Any]:
    if not req.uploads:
        raise HTTPException(status_code=400, detail="No uploads provided.")
    _sweep_stale_chunks()
    payload = []
    missing_report: List[Dict[str, Any]] = []
    for entry in req.uploads:
        if not _CHUNK_ID_RE.match(entry.upload_id):
            raise HTTPException(status_code=400, detail=f"Invalid upload_id '{entry.upload_id}'.")
        name = Path(entry.name).name
        if not name:
            raise HTTPException(status_code=400, detail="Missing file name in uploads entry.")
        d = _chunk_dir(entry.upload_id)
        parts = sorted(d.glob("*.part")) if d.exists() else []
        have = {int(p.stem) for p in parts}
        total = entry.total_chunks
        missing = sorted(set(range(total)) - have)
        if missing:
            missing_report.append({"name": name, "upload_id": entry.upload_id, "missing": missing[:50]})
            continue
        total_size = sum(p.stat().st_size for p in parts)
        if total_size > _MAX_ASSEMBLED_BYTES:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=413, detail=f"Assembled file '{name}' exceeds {_MAX_ASSEMBLED_BYTES // (1024*1024)} MB limit.")
        assembled = b"".join((d / f"{i:06d}.part").read_bytes() for i in range(total))
        payload.append((name, assembled))
        shutil.rmtree(d, ignore_errors=True)
    if missing_report:
        # 409 Conflict: client should re-upload the missing chunk indexes, then retry.
        raise HTTPException(status_code=409, detail={"message": "Some chunks are missing on this server instance. Re-upload the missing indexes and retry.", "uploads": missing_report})
    orch = ImportOrchestrator(DB_PATH, DATA_ROOT)
    return orch.stage_uploaded_files(payload, source_label="Manual UI Upload")


@app.post("/api/imports/commit")
def api_commit_imports(req: CommitBatchRequest) -> Dict[str, Any]:
    orch = ImportOrchestrator(DB_PATH, DATA_ROOT)
    try:
        res = orch.commit_staged_batch(req.batch_uuid, allow_revisions=req.allow_revisions)
        invalidate_api_cache()
        if res.get("status") != "ALREADY_COMMITTED" and (res.get("new_records", 0) > 0 or res.get("revisions_count", 0) > 0):
            res["cloud_sync"] = CloudSyncService(DB_PATH).push_db_after_update(f"Import commit {req.batch_uuid[:8]}")
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/imports/discard")
def api_discard_staged_batch(req: CommitBatchRequest) -> Dict[str, Any]:
    """Discard a STAGED or FAILED batch (safe cleanup of in-memory-only staging leftovers).
    COMMITTED batches are NEVER deleted — canonical data always stays intact."""
    from psx_app.database.schema import get_connection
    with get_connection(DB_PATH) as c:
        row = c.execute(
            "SELECT id, status FROM import_batches WHERE batch_uuid = ?",
            (req.batch_uuid,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Batch '{req.batch_uuid}' not found.")
        if row["status"] == "COMMITTED":
            raise HTTPException(status_code=400, detail="Committed batches cannot be discarded (canonical data is protected).")
        now = datetime.now(timezone.utc).isoformat()
        c.execute("UPDATE import_batches SET status = 'DISCARDED' WHERE batch_uuid = ?", (req.batch_uuid,))
        c.execute(
            "INSERT INTO audit_events (event_type, actor, details_json, created_at) VALUES ('BATCH_DISCARDED', 'local_user', ?, ?)",
            (json.dumps({"batch_uuid": req.batch_uuid, "previous_status": row["status"]}), now),
        )
        c.commit()
    invalidate_api_cache()
    return {"discarded": True, "batch_uuid": req.batch_uuid, "previous_status": row["status"]}


@app.get("/api/imports/history")
def api_imports_history() -> Dict[str, Any]:
    repo = Repository(DB_PATH)
    ov = repo.get_system_overview()
    enriched = []
    from psx_app.database.schema import get_connection
    with get_connection(DB_PATH) as c:
        staging_dir = DATA_ROOT / "data" / "staging"
        for b in ov["recent_batches"]:
            item = dict(b)
            filenames = []
            try:
                sj = json.loads(item.get("summary_json") or "{}")
                filenames = [f.get("filename") for f in sj.get("files", []) if f.get("filename")]
            except Exception:
                filenames = []
            item["filenames"] = filenames
            buuid = item.get("batch_uuid") or ""
            item["staged_resumable"] = bool(
                item.get("status") == "STAGED" and (staging_dir / buuid / "manifest.json").exists()
            )
            if item.get("status") == "DISCARDED":
                continue
            enriched.append(item)
    return {
        "batches": enriched,
        "cloud_sync": CloudSyncService(DB_PATH).get_status(),
    }


# ------------------------------------------------------------------
# 3. Module A — Top 5 Volume & Rate Register Endpoints
# ------------------------------------------------------------------
@app.get("/api/top5/register")
def api_top5_register(
    ticker: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> Dict[str, Any]:
    cache_key = f"top5_reg:{ticker}:{start_date}:{end_date}:{search}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = Top5Service(DB_PATH)
    res = svc.get_register(ticker=ticker, start_date=start_date, end_date=end_date, search=search)
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/top5/trend/{ticker}")
def api_top5_trend(ticker: str) -> Dict[str, Any]:
    cache_key = f"top5_trend:{ticker.upper()}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = Top5Service(DB_PATH)
    res = svc.get_ticker_trend(ticker)
    _API_CACHE[cache_key] = res
    return res


# ------------------------------------------------------------------
# 4 & 5. Module B — Account 91404 & 91269 Endpoints
# ------------------------------------------------------------------
@app.get("/api/accounts/{account_id}")
def api_account_report(account_id: str, selected_date: Optional[str] = Query(None)) -> Dict[str, Any]:
    if account_id not in AUTHORIZED_ACCOUNTS:
        raise HTTPException(
            status_code=400,
            detail=f"Account {account_id} is not an authorized primary account ({AUTHORIZED_ACCOUNTS}).",
        )
    cache_key = f"acc:{account_id}:{selected_date}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = AccountService(DB_PATH)
    res = svc.get_account_report(account_id, selected_date=selected_date)
    _API_CACHE[cache_key] = res
    return res


# ------------------------------------------------------------------
# 6. Module C — Futures Comparison & Annualized Analysis Endpoints
# ------------------------------------------------------------------
@app.get("/api/futures/metadata")
def api_futures_metadata(apply_rolling: bool = Query(True)) -> Dict[str, Any]:
    cache_key = f"fut_meta:{apply_rolling}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = FuturesService(DB_PATH)
    res = svc.get_metadata(apply_rolling=apply_rolling)
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/futures/comparison")
def api_futures_comparison(
    view_mode: str = Query("monthly_comparison"),
    selected_date: Optional[str] = Query(None),
    contract_month: Optional[str] = Query(None),
    base_symbol: Optional[str] = Query(None),
    days: int = Query(30),
    apply_rolling: bool = Query(True),
) -> Dict[str, Any]:
    cache_key = f"fut_comp:{view_mode}:{selected_date}:{contract_month}:{base_symbol}:{days}:{apply_rolling}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = FuturesService(DB_PATH)
    res = svc.get_comparison_rows(
        view_name=view_mode,
        selected_date=selected_date,
        contract_month=contract_month,
        base_symbol=base_symbol,
        days=days,
        apply_rolling=apply_rolling,
    )
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/futures/symbol-summary")
def api_futures_symbol_summary(
    contract_symbol: Optional[str] = Query(None),
    apply_rolling: bool = Query(True),
) -> Dict[str, Any]:
    cache_key = f"fut_sym:{contract_symbol}:{apply_rolling}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = FuturesService(DB_PATH)
    res = svc.get_future_symbol_summary(contract_symbol=contract_symbol, apply_rolling=apply_rolling)
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/futures/date-summary")
def api_futures_date_summary(
    selected_date: Optional[str] = Query(None),
    apply_rolling: bool = Query(True),
) -> Dict[str, Any]:
    cache_key = f"fut_date:{selected_date}:{apply_rolling}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = FuturesService(DB_PATH)
    res = svc.get_date_summary(selected_date=selected_date, apply_rolling=apply_rolling)
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/futures/rolling-window-preview")
def api_futures_rolling_preview(months: int = Query(2)) -> Dict[str, Any]:
    svc = FuturesService(DB_PATH)
    return svc.preview_rolling_window_cleanup(months=months)


# ------------------------------------------------------------------
# 7. Module D — Technical Analysis & 36-Ticker Dashboard Endpoints
# ------------------------------------------------------------------
@app.get("/api/technical/universe")
def api_technical_universe(
    scope: str = Query("core36"),
    search: Optional[str] = Query(None),
    signal_filter: Optional[str] = Query(None),
) -> Dict[str, Any]:
    cache_key = f"tech_uni:{scope}:{search}:{signal_filter}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = TechnicalService(DB_PATH)
    res = svc.get_universe_summary(scope=scope, search=search, signal_filter=signal_filter)
    _API_CACHE[cache_key] = res
    return res


@app.get("/api/technical/ticker/{symbol}")
def api_technical_ticker(symbol: str, tail_bars: int = Query(120)) -> Dict[str, Any]:
    cache_key = f"tech_tkr:{symbol.upper()}:{tail_bars}"
    if cache_key in _API_CACHE:
        return _API_CACHE[cache_key]
    svc = TechnicalService(DB_PATH)
    res = svc.get_ticker_analysis(symbol, tail_bars=tail_bars)
    _API_CACHE[cache_key] = res
    return res


# ------------------------------------------------------------------
# 8. Data Quality & Reconciliation Endpoints
# ------------------------------------------------------------------
@app.get("/api/reconciliation")
def api_reconciliation() -> Dict[str, Any]:
    if "reconciliation" in _API_CACHE:
        return _API_CACHE["reconciliation"]
    svc = ReconciliationService(DB_PATH)
    res = {
        "data_quality": svc.get_data_quality_report(),
        "legacy_reconciliation": svc.reconcile_against_legacy_workbooks(),
    }
    _API_CACHE["reconciliation"] = res
    return res


# ------------------------------------------------------------------
# 9. Exports, Documentation & Verified Skills Endpoints
# ------------------------------------------------------------------
@app.get("/api/exports/generate/{target}")
def api_generate_export(
    target: str,
    selected_date: Optional[str] = Query(None),
    selected_contract: Optional[str] = Query(None),
    selected_symbol: Optional[str] = Query(None),
    days: int = Query(30),
) -> FileResponse:
    exp = ExportService(DB_PATH, DATA_ROOT)
    t = target.lower()
    if t == "top5_xlsx":
        path = exp.export_top5_workbook()
    elif t == "account_91404_xlsx":
        path = exp.export_account_workbook("91404")
    elif t == "account_91269_xlsx":
        path = exp.export_account_workbook("91269")
    elif t == "futures_xlsx":
        path = exp.export_futures_workbook(
            selected_date=selected_date,
            selected_contract=selected_contract,
            selected_symbol=selected_symbol,
            days=days,
        )
    elif t == "technical_xlsx":
        path = exp.export_technical_workbook()
    elif t in ("csv_top5", "csv_91404", "csv_91269", "csv_futures", "csv_equity"):
        mod = t.replace("csv_", "")
        path = exp.export_csv_extract(mod)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export target '{target}'.")

    media = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if path.suffix == ".xlsx"
        else "text/csv"
    )
    return FileResponse(path=str(path), filename=path.name, media_type=media)


@app.get("/api/docs")
def api_list_docs() -> Dict[str, Any]:
    docs_list = []
    if DOCS_DIR.exists():
        for p in sorted(DOCS_DIR.glob("*.md")):
            docs_list.append({"name": p.name, "size_bytes": p.stat().st_size})
    readme_p = APP_ROOT.parent / "README.md"
    if readme_p.exists():
        docs_list.insert(0, {"name": "README.md", "size_bytes": readme_p.stat().st_size})
    skills_cat = []
    cat_p = SKILLS_DIR / "catalog.json"
    if cat_p.exists():
        skills_cat = json.loads(cat_p.read_text(encoding="utf-8")).get("skills", [])
    return {"docs": docs_list, "skills": skills_cat}


@app.get("/api/docs/{doc_name}")
def api_get_doc(doc_name: str) -> Dict[str, Any]:
    safe_name = Path(doc_name).name
    p = (APP_ROOT.parent / "README.md") if safe_name == "README.md" else (DOCS_DIR / safe_name)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"name": safe_name, "content": p.read_text(encoding="utf-8")}


# ------------------------------------------------------------------
# 10. Settings & Backup Endpoints
# ------------------------------------------------------------------
@app.get("/api/settings")
def api_get_settings() -> Dict[str, Any]:
    repo = Repository(DB_PATH)
    b_svc = BackupService(DB_PATH, DATA_ROOT)
    return {
        "settings": repo.get_settings(),
        "rule_versions": repo.get_rule_versions(),
        "backups": b_svc.list_backups(),
        "db_integrity": b_svc.run_integrity_check(),
        "cloud_sync": CloudSyncService(DB_PATH).get_status(),
    }


@app.post("/api/settings")
def api_update_settings(req: UpdateSettingsRequest) -> Dict[str, Any]:
    repo = Repository(DB_PATH)
    updated = repo.update_settings(req.updates, notes=req.notes)
    invalidate_api_cache()
    sync_res = CloudSyncService(DB_PATH).push_db_after_update("Settings updated")
    return {
        "settings": updated,
        "rule_versions": repo.get_rule_versions(),
        "cloud_sync": sync_res,
    }


@app.post("/api/cloud-sync/sync-now")
def api_cloud_sync_now() -> Dict[str, Any]:
    return CloudSyncService(DB_PATH).push_db_after_update("Manual cloud sync snapshot")


@app.get("/api/cloud-sync/download-snapshot")
def api_download_cloud_snapshot() -> FileResponse:
    gz_path = CloudSyncService(DB_PATH).create_local_gzip_snapshot()
    return FileResponse(path=str(gz_path), filename="latest_cloud_sync.db.gz", media_type="application/gzip")


@app.post("/api/backups/create")
def api_create_backup(req: CreateBackupRequest) -> Dict[str, Any]:
    b_svc = BackupService(DB_PATH, DATA_ROOT)
    created = b_svc.create_backup(label=req.label, include_raw_archive=req.include_raw_archive)
    return {"created": created, "backups": b_svc.list_backups()}


@app.post("/api/backups/restore")
def api_restore_backup(req: RestoreBackupRequest) -> Dict[str, Any]:
    b_svc = BackupService(DB_PATH, DATA_ROOT)
    try:
        res = b_svc.restore_backup(req.zip_filename)
        invalidate_api_cache()
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/backups/download/{zip_filename}")
def api_download_backup(zip_filename: str) -> FileResponse:
    b_svc = BackupService(DB_PATH, DATA_ROOT)
    p = b_svc.backups_dir / Path(zip_filename).name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Backup file not found.")
    return FileResponse(path=str(p), filename=p.name, media_type="application/zip")


# Mount Static Frontend SPA & Explicit Root Asset Routes for Serverless (Vercel) Compatibility
STATIC_DIR = APP_ROOT / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", include_in_schema=False)
def serve_spa_index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"), media_type="text/html")


@app.get("/styles.css", include_in_schema=False)
def serve_spa_css() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "styles.css"), media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def serve_spa_js() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "app.js"), media_type="application/javascript")


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
