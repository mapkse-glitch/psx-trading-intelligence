"""Date Normalization & Integrity repair.

Represents the remediation for the day/month swap defect: rows whose
``trade_date`` was stored as MM-DD instead of DD-MM (or vice versa) because a
text date like ``10/12/2026`` was parsed with the wrong day-first policy.
Those phantom rows hide real trading days from the calendar pickers, collapse
Symbol Filter windows (pool anchored on a fake max date such as 2026-12-10)
and corrupt the futures/equity histories.

Detection is anchor-driven and fully deterministic:
  * anchor dates = stored dates whose DAY > 12 (they cannot be swapped, so
    they define the true data season);
  * a stored date ``d`` (day <= 12) outside the season is eligible for repair
    when flipping its day/month fields lands it inside the season (49-day
    grace protects the genuine early-season rows);
  * a stored date ``d`` INSIDE the season can still be a phantom: text files
    (.csv) were the only source of swapped parses (workbooks hold real date
    cells), so a .csv-sourced row whose flip lands inside the season AND has
    an equal-measure duplicate sitting at the flipped date is dropped as
    residual pollution. Workbook-sourced rows are never touched by this rule
    and in-window rows are never moved — only provable duplicates are dropped.

Collision policy when the repaired date already has a row for the same key:
  * all measure values identical     -> drop the flipped row (true duplicate);
  * differing values                 -> keep the row whose source file is a
    structured .xlsx (real date cells, immune to the defect); otherwise keep
    the row that needed no repair; the loser is quarantined to import_issues.

The plan endpoint is a pure read (dry run). Apply runs in ONE transaction with
a pre-repair copy of the database and an audit_events entry, and is
idempotent: running it a second time repairs nothing.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from psx_app.config import DATA_ROOT, DB_PATH
from psx_app.database.schema import get_connection

SEASON_GRACE_DAYS = 49

REPAIR_TABLES: List[Dict[str, Any]] = [
    {
        "table": "futures_ohlcv", "module": "FUTURES", "date_col": "trade_date",
        "key_cols": ["trade_date", "contract_symbol"],
        "measure_cols": ["volume", "pr_close", "high", "low", "open", "close", "avg_price", "change_val"],
    },
    {
        "table": "equity_ohlcv", "module": "EQUITY", "date_col": "trade_date",
        "key_cols": ["trade_date", "symbol"],
        "measure_cols": ["volume", "pr_close", "high", "low", "open", "close", "avg_price"],
    },
    {
        "table": "index_ohlcv", "module": "INDEX", "date_col": "trade_date",
        "key_cols": ["trade_date"],
        "measure_cols": ["pr_close", "open", "high", "low", "close"],
    },
    {
        "table": "top5_volume_records", "module": "TOP5", "date_col": "trade_date",
        "key_cols": ["trade_date", "ticker", "rank"],
        "measure_cols": ["rate", "volume", "trades"],
    },
    {
        "table": "trade_executions", "module": "TRADES", "date_col": "trade_date",
        "key_cols": ["trade_date", "account_id", "unique_trade_key"],
        "measure_cols": ["quantity", "price", "trade_value"],
    },
    {
        "table": "account_daily_symbol_summary", "module": "ACCOUNTS", "date_col": "trade_date",
        "key_cols": ["trade_date", "account_id", "symbol", "market_type"],
        "measure_cols": ["buy_qty", "sell_qty", "net_pnl"],
    },
]


def _flip_day_month(iso: str) -> Optional[str]:
    try:
        y, m, d = int(iso[0:4]), int(iso[5:7]), int(iso[8:10])
    except (ValueError, IndexError):
        return None
    if m == d:
        return None  # flipping is a no-op
    try:
        return date(y, d, m).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _as_date(iso: str) -> Optional[date]:
    try:
        return date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10]))
    except (ValueError, IndexError):
        return None


class DateRepairService:
    def __init__(self, db_path: Optional[Path] = None, data_root: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.data_root = Path(data_root) if data_root else DATA_ROOT

    def _fingerprint(self, conn):
        import hashlib
        digest = hashlib.sha256()
        for cfg in REPAIR_TABLES:
            digest.update(cfg["table"].encode())
            for row in conn.execute(f"SELECT * FROM {cfg['table']} ORDER BY id"):
                digest.update(json.dumps(tuple(row), default=str, separators=(",", ":")).encode())
        return digest.hexdigest()

    # ------------------------------------------------------------------ plan
    def plan(self) -> Dict[str, Any]:
        out_sections: List[Dict[str, Any]] = []
        totals = {"candidates": 0, "move": 0, "duplicate_drop": 0, "conflict": 0}
        with get_connection(self.db_path) as conn:
            for cfg in REPAIR_TABLES:
                section = self._plan_table(conn, cfg)
                out_sections.append(section)
                for k in ("candidates", "move", "duplicate_drop", "conflict"):
                    totals[k] += section[k]
            plan_token = self._fingerprint(conn)
        return {
            "plan_token": plan_token,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "totals": totals,
            "tables": out_sections,
            "note": (
                "Dry run only. Apply performs the listed repairs in one "
                "transaction, keeps a pre-repair database copy and writes an "
                "audit event. Re-running afterwards repairs 0 rows."
            ),
        }

    def _plan_table(self, conn, cfg: Dict[str, Any]) -> Dict[str, Any]:
        table = cfg["table"]
        meta, entries = self._collect(conn, cfg)
        total_rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if meta is None:
            return {
                "table": table, "module": cfg["module"], "anchors": None,
                "total_rows": total_rows,
                "candidates": 0, "move": 0, "duplicate_drop": 0, "conflict": 0,
                "samples": [], "skipped": "no unambiguous (day>12) anchor dates",
            }
        by_action = {"MOVE": 0, "DROP_DUPLICATE": 0, "CONFLICT_MOVE": 0, "CONFLICT_DROP": 0}
        for c in entries:
            by_action[c["action"]] += 1
        return {
            "table": table, "module": cfg["module"],
            "anchors": meta,
            "total_rows": total_rows,
            "candidates": len(entries),
            "move": by_action["MOVE"] + by_action["CONFLICT_MOVE"],
            "duplicate_drop": by_action["DROP_DUPLICATE"],
            "conflict": by_action["CONFLICT_MOVE"] + by_action["CONFLICT_DROP"],
            "samples": [self._sample_view(cfg, e) for e in entries[:8]],
        }

    def _collect(self, conn, cfg: Dict[str, Any]):
        """Return (anchors_meta, full candidate entries) for one table."""
        table = cfg["table"]
        date_col = cfg["date_col"]
        anchors = [
            r[0] for r in conn.execute(
                f"SELECT DISTINCT {date_col} FROM {table} "
                f"WHERE CAST(substr({date_col}, 9, 2) AS INT) > 12 ORDER BY 1"
            ).fetchall()
        ]
        if not anchors:
            return None, []
        anchor_min, anchor_max = anchors[0], anchors[-1]
        season_head = (_as_date(anchor_min) - timedelta(days=SEASON_GRACE_DAYS)).strftime("%Y-%m-%d")
        meta = {"min": anchor_min, "max": anchor_max, "season_head": season_head}

        entries: List[Dict[str, Any]] = []
        for row in conn.execute(f"SELECT * FROM {table}").fetchall():
            r = dict(row)
            d = r[date_col]
            if not isinstance(d, str) or len(d) < 10:
                continue
            try:
                day_field = int(d[8:10])
            except ValueError:
                continue
            if day_field > 12:
                continue
            cand = _flip_day_month(d)
            if not cand or not (season_head <= cand <= anchor_max):
                continue
            in_season = season_head <= d <= anchor_max
            src = str(r.get("source_filename") or "").lower()
            if in_season:
                # Residual pollution rule: phantoms only ever came from .csv
                # text files; require an equal-measure duplicate at the true
                # date. Never MOVE an in-window row, never touch .xlsx rows.
                if not src.endswith(".csv"):
                    continue
                existing = self._find_key_row(conn, cfg, r, cand)
                if existing is None or not self._measures_equal(cfg, r, existing):
                    continue
                if self._measures_all_empty(cfg, r):
                    continue
                entries.append({"id": r["id"], "from": d, "to": cand, "action": "DROP_DUPLICATE",
                                "in_window_dup": True})
                continue
            entry = {"id": r["id"], "from": d, "to": cand, "action": "MOVE"}
            existing = self._find_key_row(conn, cfg, r, cand)
            if existing is not None:
                if self._measures_equal(cfg, r, existing):
                    entry["action"] = "DROP_DUPLICATE"
                else:
                    keep_new = self._prefer_row(r, existing)
                    entry["action"] = "CONFLICT_MOVE" if keep_new == "flipped" else "CONFLICT_DROP"
                    entry["conflict_with_id"] = existing["id"]
            entries.append(entry)
        return meta, entries

    @staticmethod
    def _sample_view(cfg, e: Dict[str, Any]) -> Dict[str, Any]:
        return {k: e[k] for k in ("id", "from", "to", "action") if k in e}

    # ----------------------------------------------------------------- apply
    def apply(self, expected_plan_token: Optional[str] = None) -> Dict[str, Any]:
        plan = self.plan()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.data_root / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        from psx_app.services.backup_service import BackupService
        backup = BackupService(self.db_path, self.data_root).create_backup(label="pre_date_repair")
        backup_path = Path(backup["zip_path"])

        applied: List[Dict[str, Any]] = []
        quarantined = 0
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if expected_plan_token and self._fingerprint(conn) != expected_plan_token:
                raise ValueError("Database changed since the dry-run plan. Run Scan again and review the new plan before applying.")
            for cfg in REPAIR_TABLES:
                table, date_col = cfg["table"], cfg["date_col"]
                _meta, fresh_plan = self._collect(conn, cfg)
                for entry in fresh_plan:
                    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (entry["id"],)).fetchone()
                    if row is None:
                        continue
                    r = dict(row)
                    cand = entry["to"]
                    existing = self._find_key_row(conn, cfg, r, cand)
                    action = entry["action"]
                    if action == "MOVE":
                        conn.execute(
                            f"UPDATE {table} SET {date_col}=? WHERE id=?", (cand, entry["id"])
                        )
                    elif action == "DROP_DUPLICATE":
                        conn.execute(f"DELETE FROM {table} WHERE id=?", (entry["id"],))
                    elif action == "CONFLICT_MOVE":
                        if existing is not None:
                            self._quarantine(conn, cfg, existing, entry)
                            conn.execute(f"DELETE FROM {table} WHERE id=?", (existing["id"],))
                            quarantined += 1
                        conn.execute(
                            f"UPDATE {table} SET {date_col}=? WHERE id=?", (cand, entry["id"])
                        )
                    elif action == "CONFLICT_DROP":
                        self._quarantine(conn, cfg, r, entry)
                        conn.execute(f"DELETE FROM {table} WHERE id=?", (entry["id"],))
                        quarantined += 1
                        continue
                    applied.append({"table": table, **{k: entry[k] for k in ("id", "from", "to", "action") if k in entry}})
            conn.execute(
                "INSERT INTO audit_events (event_type, actor, details_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    "DATE_NORMALIZATION_APPLIED", "local_user",
                    json.dumps({
                        "totals": plan["totals"],
                        "applied_count": len(applied),
                        "quarantined": quarantined,
                        "backup_path": str(backup_path),
                    }),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.execute("DELETE FROM indicator_cache")
            conn.commit()

        verify = self.plan()
        return {
            "status": "APPLIED",
            "applied_count": len(applied),
            "quarantined_to_import_issues": quarantined,
            "backup_path": str(backup_path),
            "planned_totals": plan["totals"],
            "post_apply_pending": verify["totals"],
            "idempotent_check": "PASS" if verify["totals"]["candidates"] == 0 else "REVIEW",
            "samples": applied[:10],
            "next_step_hint": (
                "To restore workbook-verified values on in-window dates, re-upload "
                "the clean .xlsx yearbooks (2026F.xlsx, 2026_YEAR.xlsx, INDEX.xlsx): "
                "duplicates are ignored, differing values are updated as revisions."
            ),
        }

    # ------------------------------------------------------------- internals
    @staticmethod
    def _measures_all_empty(cfg, row: Dict[str, Any]) -> bool:
        """An all-empty/all-zero row proves nothing."""
        any_value = False
        for col in cfg["measure_cols"]:
            v = row.get(col)
            try:
                if v is not None and abs(float(v)) > 1e-9:
                    any_value = True
            except (TypeError, ValueError):
                if v:
                    any_value = True
        return not any_value

    def _find_key_row(self, conn, cfg, row: Dict[str, Any], new_date: str):
        where, params = [], []
        for k in cfg["key_cols"]:
            where.append(f"{k}=?")
            params.append(new_date if k == cfg["date_col"] else row.get(k))
        q = f"SELECT * FROM {cfg['table']} WHERE {' AND '.join(where)} AND id<>?"
        params.append(row["id"])
        rec = conn.execute(q, params).fetchone()
        return dict(rec) if rec else None

    @staticmethod
    def _measures_equal(cfg, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        for col in cfg["measure_cols"]:
            va, vb = a.get(col), b.get(col)
            if va is None and vb is None:
                continue
            try:
                if va is None or vb is None or abs(float(va) - float(vb)) > 1e-6:
                    return False
            except (TypeError, ValueError):
                if va != vb:
                    return False
        return True

    @staticmethod
    def _prefer_row(flipped: Dict[str, Any], existing: Dict[str, Any]) -> str:
        """Which row survives a value conflict: 'flipped' or 'existing'.

        Structured .xlsx sources hold real date cells (immune to the text
        defect), so an .xlsx-sourced row wins over a csv/txt-sourced one.
        Otherwise the row that needed no repair (existing) wins.
        """
        fs = str(flipped.get("source_filename") or "").lower()
        es = str(existing.get("source_filename") or "").lower()
        if fs.endswith((".xlsx", ".xls")) and not es.endswith((".xlsx", ".xls")):
            return "flipped"
        return "existing"

    @staticmethod
    def _quarantine(conn, cfg, loser: Dict[str, Any], entry: Dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO import_issues (
                batch_id, source_file_id, module, severity, issue_type,
                symbol, account_id, trade_date, row_number, message, raw_payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                loser.get("batch_id"), loser.get("source_file_id"), cfg["module"],
                "WARNING", "DATE_NORMALIZATION_COLLISION",
                loser.get("symbol") or loser.get("contract_symbol") or loser.get("ticker"),
                loser.get("account_id"), loser.get("trade_date"), None,
                f"Date normalization dropped conflicting row (action={entry.get('action')}, "
                f"flip {entry.get('from')} -> {entry.get('to')}); raw row preserved here.",
                json.dumps(loser, default=str),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
