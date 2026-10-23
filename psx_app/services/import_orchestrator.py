import hashlib
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from psx_app.config import DATA_ROOT, DB_PATH, ensure_directories
from psx_app.database.repository import Repository
from psx_app.database.schema import get_connection
from psx_app.parsers.detector import detect_file_type
from psx_app.parsers.ohlcv_parser import parse_ohlcv_file
from psx_app.parsers.top5_parser import parse_legacy_top5_workbook, parse_top5_txt
from psx_app.parsers.tradelog_parser import parse_legacy_account_workbook, parse_tradelog_content
from psx_app.services.account_service import AccountService

MAX_UPLOAD_BYTES = 150 * 1024 * 1024  # 150 MB safety cap
MAX_ZIP_FILES = 500
FORBIDDEN_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".py", ".sh", ".dll", ".scr", ".xlsm", ".docm"}


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    clean = re.sub(r"[^A-Za-z0-9._ ()-]", "_", base).strip()
    return clean or "uploaded_file"


class ImportOrchestrator:
    """
    Layer 2 — Upload, Staging, Preview, Idempotency & Atomic Batch Commit Orchestrator.
    """

    def __init__(self, db_path: Optional[Path] = None, data_root: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.data_root = data_root or DATA_ROOT
        ensure_directories(self.data_root)
        self.repo = Repository(self.db_path)
        self.account_service = AccountService(self.db_path)

    def stage_uploaded_files(
        self,
        files_payload: List[Tuple[str, bytes]],
        source_label: str = "Manual Upload",
    ) -> Dict[str, Any]:
        """
        Accepts a list of (filename, raw_bytes). Expands any .zip archives safely,
        detects file types, parses records in memory, compares against existing database
        for duplicates/revisions, saves a staged payload, and returns a rich Import Preview.
        """
        if sum(len(raw) for _, raw in files_payload) > MAX_UPLOAD_BYTES:
            raise ValueError('Upload batch exceeds the 150 MB processing limit; split it into smaller batches.')
        batch_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        expanded_files: List[Tuple[str, bytes]] = []
        stage_warnings: List[Dict[str, Any]] = []

        for orig_name, raw_bytes in files_payload:
            safe_name = sanitize_filename(orig_name)
            ext = Path(safe_name).suffix.lower()

            if len(raw_bytes) > MAX_UPLOAD_BYTES:
                stage_warnings.append({
                    "severity": "ERROR",
                    "issue_type": "FILE_TOO_LARGE",
                    "message": f"{safe_name} exceeds maximum allowed size ({MAX_UPLOAD_BYTES} bytes).",
                })
                continue

            if ext in FORBIDDEN_EXTENSIONS:
                stage_warnings.append({
                    "severity": "ERROR",
                    "issue_type": "FORBIDDEN_FILE_TYPE",
                    "message": f"Rejected executable/macro file '{safe_name}' for security.",
                })
                continue

            if ext == ".zip":
                try:
                    import io
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                        infos = zf.infolist()
                        if len(infos) > MAX_ZIP_FILES:
                            stage_warnings.append({
                                "severity": "ERROR",
                                "issue_type": "ZIP_TOO_MANY_FILES",
                                "message": f"Archive {safe_name} contains {len(infos)} entries (> {MAX_ZIP_FILES} limit).",
                            })
                            continue
                        total_uncompressed = 0
                        for info in infos:
                            if info.is_dir():
                                continue
                            # Guard against path traversal
                            member_name = sanitize_filename(info.filename)
                            m_ext = Path(member_name).suffix.lower()
                            if m_ext in FORBIDDEN_EXTENSIONS or member_name.startswith("."):
                                continue
                            total_uncompressed += info.file_size
                            if total_uncompressed > MAX_UPLOAD_BYTES * 2:
                                raise ValueError("Archive uncompressed size limit exceeded (ZIP bomb guard).")
                            expanded_files.append((member_name, zf.read(info.filename)))
                except Exception as e:
                    stage_warnings.append({
                        "severity": "ERROR",
                        "issue_type": "INVALID_ZIP",
                        "message": f"Could not extract {safe_name}: {e}",
                    })
            else:
                expanded_files.append((safe_name, raw_bytes))

        staging_batch_dir = self.data_root / "data" / "staging" / batch_uuid
        staging_batch_dir.mkdir(parents=True, exist_ok=True)

        settings = self.repo.get_settings()
        file_previews: List[Dict[str, Any]] = []
        staged_items: List[Dict[str, Any]] = []

        total_rows_read = 0
        total_rows_accepted = 0
        total_new_records = 0
        total_duplicates = 0
        total_revisions = 0
        total_rejected = 0
        all_issues: List[Dict[str, Any]] = list(stage_warnings)

        # Detect once; load only canonical modules needed by this upload.
        detections = {}
        for fname, fbytes in expanded_files:
            temp_path = staging_batch_dir / fname
            temp_path.write_bytes(fbytes)
            detections[fname] = detect_file_type(temp_path, fname)
        types = {d["file_type"] for d in detections.values()}
        with get_connection(self.db_path) as c:
            existing_hashes = {
                r["sha256_hash"]: r["filename"]
                for r in c.execute("SELECT sha256_hash, filename FROM source_files WHERE status='COMMITTED'").fetchall()
            }
            existing_top5 = {
                (r["trade_date"], r["ticker"], r["rank"]): (r["rate"], r["volume"], r["trades"])
                for r in (c.execute("SELECT trade_date, ticker, rank, rate, volume, trades FROM top5_volume_records").fetchall() if types.intersection({'TOP5_TXT', 'LEGACY_TOP5_XLSX'}) else [])
            }
            existing_exec_keys = {
                (r["account_id"], r["unique_trade_key"]): (r["quantity"], r["price"], r["trade_value"])
                for r in (c.execute("SELECT account_id, unique_trade_key, quantity, price, trade_value FROM trade_executions").fetchall() if types.intersection({'TRADELOG'}) else [])
            }
            existing_eq_keys = {}
            existing_fut_keys = {}
            existing_idx_keys = {
                r["trade_date"]: r["close"]
                for r in (c.execute("SELECT trade_date, close FROM index_ohlcv").fetchall() if types.intersection({'INDEX_OHLCV'}) else [])
            }

        loaded_dates = {"CASH": set(), "FUTURES": set()}
        for fname, fbytes in expanded_files:
            sha256 = hashlib.sha256(fbytes).hexdigest()
            temp_path = staging_batch_dir / fname
            det = detections[fname]
            ftype = det["file_type"]
            hash_already_imported = sha256 in existing_hashes

            f_rows_read = 0
            f_accepted = 0
            f_new = 0
            f_dups = 0
            f_revs = 0
            f_rejected = 0
            f_dates: List[str] = []
            f_accounts: List[str] = []
            f_symbols: List[str] = []
            f_issues: List[Dict[str, Any]] = []
            parsed_payload: Dict[str, Any] = {}

            if ftype == "TOP5_TXT":
                res = parse_top5_txt(fbytes.decode("utf-8-sig", errors="replace"), fname)
                f_rows_read = res["rows_read"]
                f_accepted = len(res["top5"])
                f_rejected = max(0, f_rows_read - res["valid_rows"])
                if res["trade_date"]:
                    f_dates = [res["trade_date"]]
                if res["ticker"]:
                    f_symbols = [res["ticker"]]
                f_issues = res["issues"]
                for rec in res["top5"]:
                    k = (rec["trade_date"], rec["ticker"], rec["rank"])
                    if k not in existing_top5:
                        f_new += 1
                    elif existing_top5[k] == (rec["rate"], rec["volume"], rec["trades"]):
                        f_dups += 1
                    else:
                        f_revs += 1
                parsed_payload = {"top5": res["top5"]}

            elif ftype == "TRADELOG":
                res = parse_tradelog_content(fbytes.decode("utf-8-sig", errors="replace"), fname, settings)
                f_rows_read = res["rows_read"]
                f_accepted = len(res["executions"])
                f_rejected = f_rows_read - f_accepted
                f_dates = res["detected_dates"]
                f_accounts = sorted({r["account_id"] for r in res["executions"]})
                f_symbols = sorted({r["symbol"] for r in res["executions"]})
                f_issues = res["issues"]
                for ex in res["executions"]:
                    k = (ex["account_id"], ex["unique_trade_key"])
                    if k not in existing_exec_keys:
                        f_new += 1
                    elif existing_exec_keys[k] == (ex["quantity"], ex["price"], ex["trade_value"]):
                        f_dups += 1
                    else:
                        f_revs += 1
                parsed_payload = {"executions": res["executions"]}

            elif ftype in ("OHLCV_CASH", "OHLCV_FUTURES", "INDEX_OHLCV"):
                mode = "CASH" if ftype == "OHLCV_CASH" else ("FUTURES" if ftype == "OHLCV_FUTURES" else "INDEX")
                res = parse_ohlcv_file(temp_path, mode=mode, original_filename=fname)
                if mode in loaded_dates:
                    from psx_app.database.selected_rows import date_rows
                    dates = {r['trade_date'] for r in res['records']} - loaded_dates[mode]
                    table, key = ('equity_ohlcv', 'symbol') if mode == 'CASH' else ('futures_ohlcv', 'contract_symbol')
                    with get_connection(self.db_path) as lookup:
                        rows = date_rows(lookup, table, dates)
                        target = existing_eq_keys if mode == 'CASH' else existing_fut_keys
                        target.update({(r['trade_date'], r[key]): tuple(r[col] for col in ('volume','pr_close','high','low','open','close','avg_price')) for r in rows})
                    loaded_dates[mode].update(dates)
                f_rows_read = res["rows_read"]
                f_accepted = len(res["records"])
                f_rejected = max(0, f_rows_read - f_accepted)
                f_dates = [res["dates"][0], res["dates"][-1]] if res.get("dates") else []
                f_issues = res["issues"]
                for rec in res["records"]:
                    if mode == "CASH":
                        k = (rec["trade_date"], rec["symbol"])
                        if k not in existing_eq_keys:
                            f_new += 1
                            existing_eq_keys[k] = tuple(rec[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price"))
                        elif existing_eq_keys[k] == tuple(rec[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price")):
                            f_dups += 1
                        else:
                            f_revs += 1
                    elif mode == "FUTURES":
                        k = (rec["trade_date"], rec["contract_symbol"])
                        if k not in existing_fut_keys:
                            f_new += 1
                            existing_fut_keys[k] = tuple(rec[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price"))
                        elif existing_fut_keys[k] == tuple(rec[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price")):
                            f_dups += 1
                        else:
                            f_revs += 1
                    else:
                        k_idx = rec["trade_date"]
                        if k_idx not in existing_idx_keys:
                            f_new += 1
                            existing_idx_keys[k_idx] = rec["close"]
                        elif abs(existing_idx_keys[k_idx] - rec["close"]) < 1e-6:
                            f_dups += 1
                        else:
                            f_revs += 1
                parsed_payload = {"mode": mode, "records": res["records"], "typed_date_source": res.get("typed_date_source", False)}

            elif ftype == "LEGACY_TOP5_XLSX":
                res = parse_legacy_top5_workbook(temp_path)
                f_rows_read = len(res["records"])
                f_accepted = f_rows_read
                dates_s = sorted({r["trade_date"] for r in res["records"]})
                f_dates = [dates_s[0], dates_s[-1]] if dates_s else []
                f_symbols = sorted({r["ticker"] for r in res["records"]})
                for rec in res["records"]:
                    k = (rec["trade_date"], rec["ticker"], rec["rank"])
                    if k not in existing_top5:
                        f_new += 1
                        existing_top5[k] = (rec["rate"], rec["volume"], rec["trades"])
                    elif existing_top5[k] == (rec["rate"], rec["volume"], rec["trades"]):
                        f_dups += 1
                    else:
                        f_revs += 1
                parsed_payload = {"top5": res["records"]}

            elif ftype == "LEGACY_ACCOUNT_XLSX":
                res = parse_legacy_account_workbook(temp_path)
                f_rows_read = len(res["symbol_rows"])
                f_accepted = f_rows_read
                dates_s = sorted({r["trade_date"] for r in res["symbol_rows"]})
                f_dates = [dates_s[0], dates_s[-1]] if dates_s else []
                f_accounts = [res["account_id"]] if res["account_id"] else []
                f_symbols = sorted({r["symbol"] for r in res["symbol_rows"]})
                f_new = f_rows_read
                parsed_payload = {"legacy_account_rows": res["symbol_rows"], "account_id": res["account_id"]}

            else:
                f_issues.append({
                    "severity": "WARNING",
                    "issue_type": "UNRECOGNIZED_SCHEMA",
                    "message": f"File '{fname}' detected as '{ftype}'. Use Custom Column Mapping or standard PSX files.",
                })

            if hash_already_imported:
                f_issues.append({
                    "severity": "INFO",
                    "issue_type": "IDENTICAL_FILE_HASH",
                    "message": f"Exact SHA-256 hash ({sha256[:12]}) was already imported previously; duplicate records will be safely ignored.",
                })

            total_rows_read += f_rows_read
            total_rows_accepted += f_accepted
            total_new_records += f_new
            total_duplicates += f_dups
            total_revisions += f_revs
            total_rejected += f_rejected
            for iss in f_issues:
                all_issues.append({**iss, "filename": fname, "module": det.get("module", "GENERAL")})

            preview_entry = {
                "filename": fname,
                "file_type": ftype,
                "module": det.get("module", "UNKNOWN"),
                "sha256": sha256,
                "size_bytes": len(fbytes),
                "hash_already_imported": hash_already_imported,
                "detected_dates": f_dates,
                "detected_accounts": f_accounts,
                "detected_symbols": f_symbols[:30],
                "symbols_count": len(f_symbols),
                "rows_read": f_rows_read,
                "rows_accepted": f_accepted,
                "new_records": f_new,
                "duplicates_ignored": f_dups,
                "revisions_count": f_revs,
                "rows_rejected": f_rejected,
                "issues": f_issues,
            }
            file_previews.append(preview_entry)
            staged_items.append({
                "meta": preview_entry,
                "temp_path": str(temp_path),
                "payload": parsed_payload,
            })

        # Save staged manifest
        manifest = {
            "batch_uuid": batch_uuid,
            "created_at": now,
            "source_label": source_label,
            "files_count": len(file_previews),
            "rows_read": total_rows_read,
            "rows_accepted": total_rows_accepted,
            "new_records": total_new_records,
            "duplicates_ignored": total_duplicates,
            "revisions_count": total_revisions,
            "rows_rejected": total_rejected,
            "warnings_count": len(all_issues),
            "files": file_previews,
            "issues": all_issues,
        }
        (staging_batch_dir / "manifest.json").write_text(json.dumps({"manifest": manifest, "items": staged_items}), encoding="utf-8")

        with get_connection(self.db_path) as c:
            c.execute(
                """
                INSERT INTO import_batches (
                    batch_uuid, created_at, status, source_label,
                    files_count, rows_read, rows_accepted, new_records,
                    duplicates_ignored, revisions_count, rows_rejected,
                    warnings_count, summary_json
                ) VALUES (?, ?, 'STAGED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_uuid, now, source_label,
                    len(file_previews), total_rows_read, total_rows_accepted, total_new_records,
                    total_duplicates, total_revisions, total_rejected,
                    len(all_issues), json.dumps(manifest),
                ),
            )
            from psx_app.database.turso import enabled
            if enabled():
                from psx_app.services.remote_staging import put, pack
                put('stage:' + batch_uuid, pack({'manifest': manifest, 'items': staged_items}), conn=c)
            c.commit()

        from psx_app.database.turso import enabled
        if enabled():
            shutil.rmtree(staging_batch_dir, ignore_errors=True)
        return manifest

    def commit_staged_batch(self, batch_uuid: str, allow_revisions: bool = True) -> Dict[str, Any]:
        """
        Atomically commit a previously staged batch into the canonical SQLite database.
        Archives raw files in data/raw/, inserts new records, skips exact duplicates,
        logs any revisions to source_revisions, and recalculates affected account dates
        and technical indicator caches. Rolls back completely on error.
        """
        # Database status check FIRST: re-committing an already-committed batch must be
        # cheap and safe (idempotent) even after its staging folder was cleaned up or
        # the process restarted on a different machine instance.
        with get_connection(self.db_path) as pre_conn:
            pre_row = pre_conn.execute(
                "SELECT id, status, summary_json FROM import_batches WHERE batch_uuid = ?",
                (batch_uuid,),
            ).fetchone()
        if not pre_row:
            raise ValueError(f"Batch {batch_uuid} not registered in database.")
        if pre_row["status"] == "COMMITTED":
            try:
                manifest_prev = json.loads(pre_row["summary_json"] or "{}")
            except Exception:
                manifest_prev = {"batch_uuid": batch_uuid}
            return {**manifest_prev, "status": "ALREADY_COMMITTED", "batch_id": pre_row["id"]}
        if pre_row["status"] == "DISCARDED":
            raise ValueError(f"Batch {batch_uuid} was discarded. Please re-upload the source files to create a fresh staged batch.")

        staging_batch_dir = self.data_root / "data" / "staging" / batch_uuid
        manifest_path = staging_batch_dir / "manifest.json"
        from psx_app.database.turso import enabled
        if enabled():
            from psx_app.services.remote_staging import get, unpack
            bundle = unpack(get('stage:' + batch_uuid))
        elif not manifest_path.exists():
            raise FileNotFoundError(
                f"Staged batch '{batch_uuid[:8]}...' files not found on this server instance (temporary staging is cleared on cold restarts). "
                "Please Discard this staged entry in the Import and Update Center and re-upload the original file(s)."
            )

        if not enabled():
            bundle = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = bundle["manifest"]
        staged_items = bundle["items"]
        if not manifest.get("rows_accepted"):
            raise ValueError("No importable rows were found. These files were skipped, not imported as duplicates. Check the staged file formats and issues.")
        now = datetime.now(timezone.utc).isoformat()

        raw_archive_dir = self.data_root / "data" / "raw" / batch_uuid
        if not enabled():
            raw_archive_dir.mkdir(parents=True, exist_ok=True)

        commit_settings = self.repo.get_settings()
        conn = get_connection(self.db_path)
        affected_account_dates = set()
        equity_updated = False
        actual_new = 0
        actual_dups = 0
        actual_revs = 0
        verified_date_repairs = 0

        try:
            conn.execute("BEGIN IMMEDIATE")
            batch_row = conn.execute(
                "SELECT id, status FROM import_batches WHERE batch_uuid = ?",
                (batch_uuid,),
            ).fetchone()
            if not batch_row:
                raise ValueError(f"Batch {batch_uuid} not registered in database.")
            batch_id = batch_row["id"]
            if batch_row["status"] == "COMMITTED":
                conn.rollback()
                return {**manifest, "status": "ALREADY_COMMITTED", "batch_id": batch_id}

            from collections import OrderedDict
            queued = OrderedDict()
            def queue_write(sql, values):
                queued.setdefault(sql, []).append(values)
            needs_top5 = any('top5' in i.get('payload', {}) for i in staged_items)
            needs_exec = any('executions' in i.get('payload', {}) for i in staged_items)
            top5_existing = {(r['trade_date'],r['ticker'],r['rank']): dict(r) for r in conn.execute('SELECT trade_date,ticker,rank,rate,volume,trades FROM top5_volume_records')} if needs_top5 else {}
            exec_existing = {(r['account_id'],r['unique_trade_key']): dict(r) for r in conn.execute('SELECT account_id,unique_trade_key,quantity,price,trade_value FROM trade_executions')} if needs_exec else {}

            for item in staged_items:
                meta = item["meta"]
                t_path = Path(item["temp_path"])
                arch_path = raw_archive_dir / f"{meta['sha256'][:12]}_{meta['filename']}"
                if not enabled() and t_path.exists():
                    shutil.copy2(t_path, arch_path)

                d_min = meta["detected_dates"][0] if meta["detected_dates"] else None
                d_max = meta["detected_dates"][-1] if meta["detected_dates"] else None

                cur_sf = conn.execute(
                    """
                    INSERT INTO source_files (
                        filename, file_type, sha256_hash, file_size,
                        archive_path, detected_date_min, detected_date_max,
                        uploaded_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED')
                    """,
                    (
                        meta["filename"], meta["file_type"], meta["sha256"],
                        meta["size_bytes"], ("turso:metadata-only/" + meta["filename"] if enabled() else str(arch_path)), d_min, d_max, now,
                    ),
                )
                sf_id = cur_sf.lastrowid

                for iss in meta.get("issues", []):
                    queue_write(
                        """
                        INSERT INTO import_issues (
                            batch_id, source_file_id, module, severity, issue_type,
                            symbol, account_id, trade_date, row_number, message, raw_payload, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            batch_id, sf_id, meta.get("module", "GENERAL"),
                            iss.get("severity", "WARNING"), iss.get("issue_type", "GENERAL"),
                            iss.get("symbol"), iss.get("account_id"), iss.get("trade_date"),
                            iss.get("row_number"), iss.get("message", ""), iss.get("raw_payload"), now,
                        ),
                    )

                payload = item.get("payload", {})
                ftype = meta["file_type"]

                # 1. Top 5 records
                if "top5" in payload:
                    for rec in payload["top5"]:
                        ex = top5_existing.get((rec["trade_date"], rec["ticker"], rec["rank"]))
                        if ex is None:
                            queue_write(
                                """
                                INSERT INTO top5_volume_records (
                                    trade_date, ticker, rank, rate, volume, trades,
                                    snapshot_time, source_filename, source_file_id,
                                    batch_id, origin_type, imported_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    rec["trade_date"], rec["ticker"], rec["rank"],
                                    rec["rate"], rec["volume"], rec["trades"],
                                    rec.get("snapshot_time"), rec.get("source_filename", meta["filename"]),
                                    sf_id, batch_id, rec.get("origin_type", "RAW_TXT"), now,
                                ),
                            )
                            actual_new += 1
                            top5_existing[(rec["trade_date"], rec["ticker"], rec["rank"])] = {k: rec[k] for k in ("rate", "volume", "trades")}
                        elif (ex["rate"], ex["volume"], ex["trades"]) == (rec["rate"], rec["volume"], rec["trades"]):
                            actual_dups += 1
                        else:
                            if allow_revisions:
                                queue_write(
                                    """
                                    INSERT INTO source_revisions (
                                        batch_id, table_name, business_key, old_value_json, new_value_json, reason, recorded_at
                                    ) VALUES (?, 'top5_volume_records', ?, ?, ?, 'Revised source upload', ?)
                                    """,
                                    (
                                        batch_id,
                                        f"{rec['trade_date']}|{rec['ticker']}|Rank{rec['rank']}",
                                        json.dumps(dict(ex)),
                                        json.dumps(rec),
                                        now,
                                    ),
                                )
                                conn.execute(
                                    """
                                    UPDATE top5_volume_records
                                    SET rate = ?, volume = ?, trades = ?, source_filename = ?,
                                        source_file_id = ?, batch_id = ?, imported_at = ?
                                    WHERE trade_date = ? AND ticker = ? AND rank = ?
                                    """,
                                    (
                                        rec["rate"], rec["volume"], rec["trades"],
                                        meta["filename"], sf_id, batch_id, now,
                                        rec["trade_date"], rec["ticker"], rec["rank"],
                                    ),
                                )
                                actual_revs += 1
                            else:
                                actual_dups += 1

                # 2. Trade executions
                if "executions" in payload:
                    for ex_rec in payload["executions"]:
                        ex = exec_existing.get((ex_rec["account_id"], ex_rec["unique_trade_key"]))
                        if ex is None:
                            queue_write(
                                """
                                INSERT INTO trade_executions (
                                    account_id, trade_date, trade_time, terminal_id, market_type,
                                    symbol, raw_side, normalized_side, order_id, execution_id,
                                    status, quantity, remaining_qty, order_qty, price, trade_value,
                                    commission_slab, commission_amount, sst_amount, total_charges,
                                    unique_trade_key, source_filename, source_file_id, batch_id, imported_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    ex_rec["account_id"], ex_rec["trade_date"], ex_rec["trade_time"],
                                    ex_rec["terminal_id"], ex_rec["market_type"], ex_rec["symbol"],
                                    ex_rec["raw_side"], ex_rec["normalized_side"], ex_rec["order_id"],
                                    ex_rec["execution_id"], ex_rec["status"], ex_rec["quantity"],
                                    ex_rec["remaining_qty"], ex_rec["order_qty"], ex_rec["price"],
                                    ex_rec["trade_value"], ex_rec["commission_slab"],
                                    ex_rec["commission_amount"], ex_rec["sst_amount"],
                                    ex_rec["total_charges"], ex_rec["unique_trade_key"],
                                    ex_rec["source_filename"], sf_id, batch_id, now,
                                ),
                            )
                            actual_new += 1
                            exec_existing[(ex_rec["account_id"], ex_rec["unique_trade_key"])] = {k: ex_rec[k] for k in ("quantity", "price", "trade_value")}
                            affected_account_dates.add((ex_rec["account_id"], ex_rec["trade_date"]))
                        else:
                            actual_dups += 1

                # 3. Legacy Account Symbol-Date Rows
                if "legacy_account_rows" in payload:
                    for s_rec in payload["legacy_account_rows"]:
                        ex = conn.execute(
                            """
                            SELECT origin_type, net_pnl FROM account_daily_symbol_summary
                            WHERE account_id = ? AND trade_date = ? AND symbol = ?
                            """,
                            (s_rec["account_id"], s_rec["trade_date"], s_rec["symbol"]),
                        ).fetchone()
                        if ex is None:
                            conn.execute(
                                """
                                INSERT INTO account_daily_symbol_summary (
                                    account_id, trade_date, symbol, market_type,
                                    buy_qty, buy_value, avg_buy_price,
                                    sell_qty, sell_value, avg_sell_price,
                                    price_diff, net_qty, gross_pnl,
                                    commission_slab_label, commission_amount, sst_amount,
                                    total_charges, net_pnl, return_on_buy,
                                    origin_type, source_filename, batch_id, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    s_rec["account_id"], s_rec["trade_date"], s_rec["symbol"], s_rec["market_type"],
                                    s_rec["buy_qty"], s_rec["buy_value"], s_rec["avg_buy_price"],
                                    s_rec["sell_qty"], s_rec["sell_value"], s_rec["avg_sell_price"],
                                    s_rec["price_diff"], s_rec["net_qty"], s_rec["gross_pnl"],
                                    s_rec["commission_slab_label"], s_rec["commission_amount"], s_rec["sst_amount"],
                                    s_rec["total_charges"], s_rec["net_pnl"], s_rec["return_on_buy"],
                                    s_rec.get("origin_type", "LEGACY_MIGRATED"), s_rec["source_filename"], batch_id, now,
                                ),
                            )
                            actual_new += 1
                        else:
                            actual_dups += 1

                # 4. OHLCV Cash / Futures / Index
                if "records" in payload and "mode" in payload:
                    mode = payload["mode"]
                    recs = payload["records"]
                    if payload.get("typed_date_source") and meta["filename"].lower().endswith(".xlsx") and mode in ("CASH", "FUTURES"):
                        from psx_app.services.verified_source_repair import quarantine_verified_swaps
                        repaired = quarantine_verified_swaps(conn, mode, recs, batch_id, sf_id, now)
                        verified_date_repairs += repaired
                        equity_updated = equity_updated or (mode == "CASH" and repaired > 0)
                    if mode == "CASH":
                        existing_map = {
                            (r["trade_date"], r["symbol"]): tuple(r[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price"))
                            for r in __import__("psx_app.database.selected_rows", fromlist=["date_rows"]).date_rows(conn, "equity_ohlcv", [r["trade_date"] for r in recs])
                        }
                        to_insert = []
                        for r in recs:
                            k = (r["trade_date"], r["symbol"])
                            if k not in existing_map:
                                to_insert.append((
                                    r["trade_date"], r["symbol"], r["volume"], r["pr_close"],
                                    r["high"], r["low"], r["open"], r["close"], r["avg_price"],
                                    r["source_filename"], sf_id, batch_id,
                                ))
                                existing_map[k] = tuple(r[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price"))
                                actual_new += 1
                                equity_updated = True
                            elif existing_map[k] == tuple(r[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price")):
                                actual_dups += 1
                            elif not allow_revisions:
                                actual_dups += 1
                            else:
                                conn.execute(
                                    """
                                    UPDATE equity_ohlcv
                                    SET volume=?, pr_close=?, high=?, low=?, open=?, close=?, avg_price=?,
                                        source_filename=?, source_file_id=?, batch_id=?
                                    WHERE trade_date=? AND symbol=?
                                    """,
                                    (
                                        r["volume"], r["pr_close"], r["high"], r["low"], r["open"],
                                        r["close"], r["avg_price"], r["source_filename"], sf_id, batch_id,
                                        r["trade_date"], r["symbol"],
                                    ),
                                )
                                actual_revs += 1
                                equity_updated = True
                        if to_insert:
                            conn.executemany(
                                """
                                INSERT OR IGNORE INTO equity_ohlcv (
                                    trade_date, symbol, volume, pr_close, high, low, open, close, avg_price,
                                    source_filename, source_file_id, batch_id
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                to_insert,
                            )
                    elif mode == "FUTURES":
                        existing_fmap = {
                            (r["trade_date"], r["contract_symbol"]): tuple(r[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price"))
                            for r in __import__("psx_app.database.selected_rows", fromlist=["date_rows"]).date_rows(conn, "futures_ohlcv", [r["trade_date"] for r in recs])
                        }
                        to_insert_f = []
                        for r in recs:
                            k = (r["trade_date"], r["contract_symbol"])
                            if k not in existing_fmap:
                                to_insert_f.append((
                                    r["trade_date"], r["contract_symbol"], r["base_symbol"], r["contract_month"],
                                    r["volume"], r["pr_close"], r["high"], r["low"], r["open"], r["close"],
                                    r["avg_price"], r["change_val"], r["source_filename"], sf_id, batch_id,
                                ))
                                existing_fmap[k] = tuple(r[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price"))
                                actual_new += 1
                            elif existing_fmap[k] == tuple(r[col] for col in ("volume", "pr_close", "high", "low", "open", "close", "avg_price")):
                                actual_dups += 1
                            elif not allow_revisions:
                                actual_dups += 1
                            else:
                                conn.execute(
                                    """
                                    UPDATE futures_ohlcv
                                    SET volume=?, pr_close=?, high=?, low=?, open=?, close=?, avg_price=?,
                                        change_val=?, source_filename=?, source_file_id=?, batch_id=?
                                    WHERE trade_date=? AND contract_symbol=?
                                    """,
                                    (
                                        r["volume"], r["pr_close"], r["high"], r["low"], r["open"],
                                        r["close"], r["avg_price"], r["change_val"], r["source_filename"],
                                        sf_id, batch_id, r["trade_date"], r["contract_symbol"],
                                    ),
                                )
                                actual_revs += 1
                        if to_insert_f:
                            conn.executemany(
                                """
                                INSERT OR IGNORE INTO futures_ohlcv (
                                    trade_date, contract_symbol, base_symbol, contract_month,
                                    volume, pr_close, high, low, open, close, avg_price, change_val,
                                    source_filename, source_file_id, batch_id
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                to_insert_f,
                            )
                    elif mode == "INDEX":
                        for r in recs:
                            ex_i = conn.execute(
                                "SELECT close FROM index_ohlcv WHERE trade_date = ?",
                                (r["trade_date"],),
                            ).fetchone()
                            if ex_i is None:
                                conn.execute(
                                    """
                                    INSERT INTO index_ohlcv (
                                        trade_date, pr_close, open, high, low, close,
                                        source_filename, source_file_id, batch_id
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        r["trade_date"], r["pr_close"], r["open"], r["high"],
                                        r["low"], r["close"], r["source_filename"], sf_id, batch_id,
                                    ),
                                )
                                actual_new += 1
                            else:
                                actual_dups += 1

            for sql, values in queued.items():
                conn.executemany(sql, values)

            if equity_updated:
                conn.execute("DELETE FROM indicator_cache")

            updated_manifest = {
                **manifest,
                "status": "COMMITTED",
                "committed_at": now,
                "new_records": actual_new,
                "duplicates_ignored": actual_dups,
                "revisions_count": actual_revs,
                "verified_date_repairs": verified_date_repairs,
                "affected_account_dates": [f"{a}:{d}" for a, d in sorted(affected_account_dates)],
                "reports_recalculated": [
                    "Top 5 Volume & Rate Register",
                    "Account 91404 & 91269 Summaries",
                    "Futures Comparison & Annualized Views",
                    "Technical Analysis & 36-Ticker Cache",
                ],
            }

            conn.execute(
                """
                UPDATE import_batches
                SET status = 'COMMITTED', committed_at = ?,
                    new_records = ?, duplicates_ignored = ?, revisions_count = ?,
                    summary_json = ?
                WHERE id = ?
                """,
                (now, actual_new, actual_dups, actual_revs, json.dumps(updated_manifest), batch_id),
            )
            conn.execute(
                """
                INSERT INTO audit_events (event_type, actor, details_json, created_at)
                VALUES ('BATCH_COMMITTED', 'local_user', ?, ?)
                """,
                (
                    json.dumps({
                        "batch_uuid": batch_uuid,
                        "batch_id": batch_id,
                        "new_records": actual_new,
                        "duplicates_ignored": actual_dups,
                        "revisions_count": actual_revs,
                "verified_date_repairs": verified_date_repairs,
                    }),
                    now,
                ),
            )
            for acc_id, t_date in sorted(affected_account_dates):
                self.account_service.recalculate_account_date_from_executions(acc_id, t_date, batch_id=batch_id, connection=conn, settings=commit_settings)
            if enabled():
                conn.execute('DELETE FROM psx_blob_parts WHERE scope=?', ('stage:' + batch_uuid,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.execute(
                "UPDATE import_batches SET status = 'FAILED' WHERE batch_uuid = ? AND status != 'COMMITTED'",
                (batch_uuid,),
            )
            conn.commit()
            raise e
        finally:
            conn.close()

        # Recalculate affected account dates from raw executions

        # Clean up staging directory after successful commit
        shutil.rmtree(staging_batch_dir, ignore_errors=True)
        return updated_manifest
