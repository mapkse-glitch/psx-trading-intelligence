import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import DEFAULT_SETTINGS
from psx_app.database.schema import get_connection


class Repository:
    """Database repository abstracting SQLite persistence for all 4 modules."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def get_settings(self) -> Dict[str, Any]:
        merged = dict(DEFAULT_SETTINGS)
        with self.conn() as c:
            rows = c.execute("SELECT key, value_json FROM app_settings").fetchall()
            for r in rows:
                try:
                    merged[r["key"]] = json.loads(r["value_json"])
                except Exception:
                    merged[r["key"]] = r["value_json"]
        return merged

    def update_settings(
        self,
        updates: Dict[str, Any],
        actor: str = "local_user",
        notes: str = "Updated via Settings UI",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn() as c:
            current = self.get_settings()
            rule_keys = {
                "commission_slab1_upper", "commission_slab1_paisa_per_share",
                "commission_slab2_start", "commission_slab2_rate", "sst_rate",
                "default_futures_days", "futures_rolling_months",
                "rsi_period", "macd_fast", "macd_slow", "macd_signal",
                "bb_period", "bb_std", "ema_periods", "adx_period",
                "strict_indicator_sufficiency", "signal_buy_threshold",
                "signal_sell_threshold", "signal_short_threshold"
            }
            rule_changed = any(k in updates and updates[k] != current.get(k) for k in rule_keys)
            if rule_changed:
                new_ver = int(current.get("rule_version", 1)) + 1
                updates["rule_version"] = new_ver
                c.execute("DELETE FROM indicator_cache")
            for k, v in updates.items():
                c.execute(
                    """
                    INSERT INTO app_settings (key, value_json, description, version, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        version = app_settings.version + 1,
                        updated_at = excluded.updated_at
                    """,
                    (k, json.dumps(v), f"Setting: {k}", now),
                )
            merged_after = {**current, **updates}
            c.execute(
                """
                INSERT INTO calculation_rules (module, rule_name, version, parameters_json, effective_from, created_at)
                VALUES ('ALL', ?, ?, ?, ?, ?)
                """,
                (notes, int(merged_after.get("rule_version", 1)), json.dumps(updates), now[:10], now),
            )
            c.execute(
                """
                INSERT INTO audit_events (event_type, actor, details_json, created_at)
                VALUES ('SETTINGS_UPDATED', ?, ?, ?)
                """,
                (actor, json.dumps({"updates": updates, "notes": notes, "rule_changed": rule_changed}), now),
            )
            c.commit()
        return self.get_settings()

    def get_rule_versions(self) -> List[Dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT id, module, rule_name, version, parameters_json, effective_from, created_at FROM calculation_rules ORDER BY id DESC LIMIT 25"
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["parameters"] = json.loads(d.get("parameters_json") or "{}")
                except Exception:
                    d["parameters"] = {}
                out.append(d)
            return out

    def log_audit(self, event_type: str, details: Dict[str, Any], actor: str = "local_user") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn() as c:
            c.execute(
                "INSERT INTO audit_events (event_type, actor, details_json, created_at) VALUES (?, ?, ?, ?)",
                (event_type, actor, json.dumps(details), now),
            )
            c.commit()

    def get_system_overview(self) -> Dict[str, Any]:
        with self.conn() as c:
            top5_cnt = c.execute("SELECT COUNT(*) FROM top5_volume_records").fetchone()[0]
            top5_max = c.execute("SELECT MAX(trade_date) FROM top5_volume_records").fetchone()[0]
            top5_min = c.execute("SELECT MIN(trade_date) FROM top5_volume_records").fetchone()[0]
            top5_tickers = c.execute("SELECT COUNT(DISTINCT ticker) FROM top5_volume_records").fetchone()[0]

            exec_cnt = c.execute("SELECT COUNT(*) FROM trade_executions").fetchone()[0]
            adss_cnt = c.execute("SELECT COUNT(*) FROM account_daily_symbol_summary").fetchone()[0]
            acc_dates = {
                r["account_id"]: {"min": r["min_d"], "max": r["max_d"], "days": r["days_cnt"]}
                for r in c.execute(
                    """
                    SELECT account_id, MIN(trade_date) AS min_d, MAX(trade_date) AS max_d,
                           COUNT(DISTINCT trade_date) AS days_cnt
                    FROM account_daily_symbol_summary
                    GROUP BY account_id
                    """
                ).fetchall()
            }

            eq_cnt = c.execute("SELECT COUNT(*) FROM equity_ohlcv").fetchone()[0]
            eq_max = c.execute("SELECT MAX(trade_date) FROM equity_ohlcv").fetchone()[0]
            eq_min = c.execute("SELECT MIN(trade_date) FROM equity_ohlcv").fetchone()[0]
            eq_syms = c.execute("SELECT COUNT(DISTINCT symbol) FROM equity_ohlcv").fetchone()[0]

            fut_cnt = c.execute("SELECT COUNT(*) FROM futures_ohlcv").fetchone()[0]
            fut_max = c.execute("SELECT MAX(trade_date) FROM futures_ohlcv").fetchone()[0]
            fut_min = c.execute("SELECT MIN(trade_date) FROM futures_ohlcv").fetchone()[0]
            fut_syms = c.execute("SELECT COUNT(DISTINCT contract_symbol) FROM futures_ohlcv").fetchone()[0]

            idx_cnt = c.execute("SELECT COUNT(*) FROM index_ohlcv").fetchone()[0]
            idx_max = c.execute("SELECT MAX(trade_date) FROM index_ohlcv").fetchone()[0]

            batches = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM import_batches ORDER BY id DESC LIMIT 15"
                ).fetchall()
            ]
            issues_by_sev = {
                r["severity"]: r["cnt"]
                for r in c.execute(
                    "SELECT severity, COUNT(*) AS cnt FROM import_issues GROUP BY severity"
                ).fetchall()
            }
            files_cnt = c.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]

        return {
            "data_status_badge": "HISTORICAL / EOD IMPORTED DATA (NOT LIVE FEED)",
            "top5": {
                "records": top5_cnt,
                "tickers": top5_tickers,
                "min_date": top5_min,
                "max_date": top5_max,
            },
            "accounts": {
                "raw_executions": exec_cnt,
                "daily_symbol_summaries": adss_cnt,
                "by_account": acc_dates,
            },
            "equity_ohlcv": {
                "records": eq_cnt,
                "symbols": eq_syms,
                "min_date": eq_min,
                "max_date": eq_max,
            },
            "futures_ohlcv": {
                "records": fut_cnt,
                "contracts": fut_syms,
                "min_date": fut_min,
                "max_date": fut_max,
            },
            "index_ohlcv": {
                "records": idx_cnt,
                "max_date": idx_max,
            },
            "source_files_archived": files_cnt,
            "issues_summary": issues_by_sev,
            "recent_batches": batches,
            "last_import_timestamp": batches[0]["committed_at"] if batches else None,
        }
