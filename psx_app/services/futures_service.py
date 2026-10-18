from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from psx_app.database.repository import Repository
from psx_app.database.schema import get_connection


class FuturesService:
    """
    Module C — Futures Comparison and Annualized Analysis Service.
    Provides all 7 logical views:
      1. Monthly Comparison
      2. Month Filter
      3. Symbol Filter
      4. Annualized Comparison
      5. Date Filter
      6. Future Symbol Summary
      7. Date Summary
    Enforces strict same-date matching (never forward-filling missing data; returns 'N/A').
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.repo = Repository(db_path)

    def _get_rolling_cutoff_month(self, max_date_str: Optional[str], rolling_months: int = 2) -> Optional[str]:
        """
        Calculate the earliest retained YYYY-MM under the N-month rolling retention policy.
        Example: if max_date is in 2026-10 and rolling_months=2, keep 2026-09 and 2026-10 (cutoff '2026-09-01').
        """
        if not max_date_str or rolling_months <= 0:
            return None
        dt = datetime.strptime(max_date_str[:10], "%Y-%m-%d")
        year = dt.year
        month = dt.month - (rolling_months - 1)
        while month <= 0:
            month += 12
            year -= 1
        return f"{year:04d}-{month:02d}-01"

    def get_metadata(self, apply_rolling: Optional[bool] = None) -> Dict[str, Any]:
        settings = self.repo.get_settings()
        use_rolling = settings.get("futures_apply_rolling_window", True) if apply_rolling is None else apply_rolling
        rolling_months = int(settings.get("futures_rolling_retention_months", 2))
        default_days = int(settings.get("futures_default_days", 30))

        with get_connection(self.db_path) as c:
            max_date = c.execute("SELECT MAX(trade_date) FROM futures_ohlcv").fetchone()[0]
            all_dates = [
                r[0] for r in c.execute("SELECT DISTINCT trade_date FROM futures_ohlcv ORDER BY trade_date ASC").fetchall()
            ]
            cutoff = self._get_rolling_cutoff_month(max_date, rolling_months) if use_rolling else None

            if cutoff:
                retained_dates = [d for d in all_dates if d >= cutoff]
                pruned_dates = [d for d in all_dates if d < cutoff]
            else:
                retained_dates = all_dates
                pruned_dates = []

            date_clause = "WHERE trade_date >= ?" if cutoff else ""
            params: Tuple[Any, ...] = (cutoff,) if cutoff else ()

            base_symbols = [
                r[0]
                for r in c.execute(
                    f"SELECT DISTINCT base_symbol FROM futures_ohlcv {date_clause} ORDER BY base_symbol ASC",
                    params,
                ).fetchall()
            ]
            contracts = [
                r[0]
                for r in c.execute(
                    f"SELECT DISTINCT contract_month FROM futures_ohlcv {date_clause} ORDER BY contract_month ASC",
                    params,
                ).fetchall()
            ]
            contract_symbols = [
                r[0]
                for r in c.execute(
                    f"SELECT DISTINCT contract_symbol FROM futures_ohlcv {date_clause} ORDER BY contract_symbol ASC",
                    params,
                ).fetchall()
            ]

            pruned_months = sorted({d[:7] for d in pruned_dates})
            retained_months = sorted({d[:7] for d in retained_dates})

        return {
            "latest_date": retained_dates[-1] if retained_dates else None,
            "dates": retained_dates,
            "retained_dates": retained_dates,
            "all_dates_in_db": all_dates,
            "retained_months": retained_months,
            "pruned_months_outside_window": pruned_months,
            "cutoff_date": cutoff,
            "apply_rolling_window": use_rolling,
            "rolling_retention_months": rolling_months,
            "default_days": default_days,
            "base_symbols": base_symbols,
            "contracts": contracts,
            "contract_symbols": contract_symbols,
        }

    def get_comparison_rows(
        self,
        view_name: str = "monthly_comparison",
        selected_date: Optional[str] = None,
        contract_month: Optional[str] = None,
        base_symbol: Optional[str] = None,
        days: Optional[int] = None,
        apply_rolling: Optional[bool] = None,
        view_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        if view_mode:
            view_name = view_mode
        """
        Compute comparison rows for views 1..5:
        - monthly_comparison (filter by selected_date)
        - month_filter (filter by selected_date + contract_month)
        - symbol_filter (filter by selected_date + base_symbol, plus all-dates contract series for symbol)
        - annualized_comparison (filter by selected_date, all symbols & contracts)
        - date_filter (filter by selected_date)
        All sorted by Annualized % ascending, with missing same-date values shown as 'N/A'.
        """
        meta = self.get_metadata(apply_rolling=apply_rolling)
        eff_days = int(days) if (days is not None and int(days) > 0) else meta["default_days"]
        sel_date = selected_date if selected_date else meta["latest_date"]
        sel_contract = contract_month if contract_month else (meta["contracts"][0] if meta["contracts"] else None)
        sel_symbol = base_symbol if base_symbol else ("OGDC" if "OGDC" in meta["base_symbols"] else (meta["base_symbols"][0] if meta["base_symbols"] else None))

        if not sel_date:
            return {
                "view": view_name,
                "selected_date": None,
                "days": eff_days,
                "rows": [],
                "metadata": meta,
            }

        clauses = ["f.trade_date = ?"]
        params: List[Any] = [sel_date]

        if view_name == "month_filter" and sel_contract and sel_contract != "ALL":
            clauses.append("f.contract_month = ?")
            params.append(sel_contract)
        elif view_name == "symbol_filter" and sel_symbol and sel_symbol != "ALL":
            clauses.append("f.base_symbol = ?")
            params.append(sel_symbol)

        where_sql = " AND ".join(clauses)
        # Strict same-date LEFT JOIN: e.trade_date = f.trade_date AND e.symbol = f.base_symbol
        sql = f"""
            SELECT
                f.trade_date,
                f.base_symbol AS symbol,
                f.contract_month AS contract,
                f.contract_symbol,
                e.close AS current_value,
                f.close AS future_value,
                f.volume AS volume,
                f.high AS high,
                f.low AS low
            FROM futures_ohlcv f
            LEFT JOIN equity_ohlcv e
                ON e.trade_date = f.trade_date AND e.symbol = f.base_symbol
            WHERE {where_sql}
        """

        with get_connection(self.db_path) as c:
            raw = [dict(r) for r in c.execute(sql, params).fetchall()]

        rows: List[Dict[str, Any]] = []
        missing_spot_count = 0
        for item in raw:
            curr = item["current_value"]
            fut = item["future_value"]
            vol = item["volume"]
            hi = item["high"]
            lo = item["low"]

            if curr is None or curr <= 0 or fut is None or eff_days <= 0:
                if curr is None or curr <= 0:
                    missing_spot_count += 1
                rows.append({
                    "trade_date": item["trade_date"],
                    "symbol": item["symbol"],
                    "contract": item["contract"],
                    "contract_symbol": item["contract_symbol"],
                    "current_value": curr if (curr is not None and curr > 0) else "N/A",
                    "future_value": fut if fut is not None else "N/A",
                    "volume": vol if vol is not None else "N/A",
                    "high": hi if hi is not None else "N/A",
                    "low": lo if lo is not None else "N/A",
                    "difference": "N/A",
                    "difference_pct": "N/A",
                    "days": eff_days,
                    "annualized_pct": "N/A",
                    "_sort_key": float("inf"),
                })
            else:
                diff = fut - curr
                diff_pct = (diff / curr) * 100.0
                ann_pct = (diff / curr) * (365.0 / eff_days) * 100.0
                rows.append({
                    "trade_date": item["trade_date"],
                    "symbol": item["symbol"],
                    "contract": item["contract"],
                    "contract_symbol": item["contract_symbol"],
                    "current_value": curr,
                    "future_value": fut,
                    "volume": vol if vol is not None else "N/A",
                    "high": hi if hi is not None else "N/A",
                    "low": lo if lo is not None else "N/A",
                    "difference": diff,
                    "difference_pct": diff_pct,
                    "days": eff_days,
                    "annualized_pct": ann_pct,
                    "_sort_key": ann_pct,
                })

        # Sort by Annualized % Ascending (lowest first, highest last; N/A at the end)
        rows.sort(key=lambda r: (r["_sort_key"], r["symbol"], r["contract"]))
        for r in rows:
            r.pop("_sort_key", None)

        return {
            "view": view_name,
            "selected_date": sel_date,
            "selected_contract": sel_contract,
            "selected_symbol": sel_symbol,
            "days": eff_days,
            "rows_count": len(rows),
            "missing_same_date_spot_count": missing_spot_count,
            "rows": rows,
            "metadata": meta,
        }

    def get_future_symbol_summary(
        self,
        contract_symbol: Optional[str] = None,
        apply_rolling: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        View 6: Future Symbol Summary.
        Displays ALL retained date-wise records from 2026F for the selected contract_symbol,
        sorted by DATE ascending, with Change = CLOSE - PR_CL.
        """
        meta = self.get_metadata(apply_rolling=apply_rolling)
        sel_sym = (
            contract_symbol.strip().upper()
            if contract_symbol
            else (meta["contract_symbols"][0] if meta["contract_symbols"] else None)
        )
        cutoff = meta["cutoff_date"]

        clauses = ["contract_symbol = ?"]
        params: List[Any] = [sel_sym]
        if cutoff:
            clauses.append("trade_date >= ?")
            params.append(cutoff)

        with get_connection(self.db_path) as c:
            raw = [
                dict(r)
                for r in c.execute(
                    f"""
                    SELECT trade_date, contract_symbol, pr_close, open, high, low, avg_price, close, volume
                    FROM futures_ohlcv
                    WHERE {' AND '.join(clauses)}
                    ORDER BY trade_date ASC
                    """,
                    params,
                ).fetchall()
            ]

        rows = []
        for r in raw:
            cl = r["close"]
            pr = r["pr_close"]
            chg = (cl - pr) if (cl is not None and pr is not None) else "N/A"
            rows.append({
                "DATE": r["trade_date"],
                "SYMBOL": r["contract_symbol"],
                "PR_CL": pr if pr is not None else "N/A",
                "OPEN": r["open"] if r["open"] is not None else "N/A",
                "High": r["high"] if r["high"] is not None else "N/A",
                "LOW": r["low"] if r["low"] is not None else "N/A",
                "AVG": r["avg_price"] if r["avg_price"] is not None else "N/A",
                "CLOSE": cl if cl is not None else "N/A",
                "VOLUME": r["volume"] if r["volume"] is not None else "N/A",
                "Change": chg,
            })

        return {
            "view": "future_symbol_summary",
            "selected_contract_symbol": sel_sym,
            "rows_count": len(rows),
            "rows": rows,
            "metadata": meta,
        }

    def get_date_summary(
        self,
        selected_date: Optional[str] = None,
        apply_rolling: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        View 7: Date Summary.
        Displays all available symbols and records from 2026F for the exact selected_date,
        sorted by SYMBOL ascending, with Change = CLOSE - PR_CL.
        Never uses another date's data; if no records exist, returns empty list + explicit message.
        """
        meta = self.get_metadata(apply_rolling=apply_rolling)
        sel_date = selected_date if selected_date else meta["latest_date"]

        with get_connection(self.db_path) as c:
            raw = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT trade_date, contract_symbol, pr_close, open, high, low, avg_price, close, volume
                    FROM futures_ohlcv
                    WHERE trade_date = ?
                    ORDER BY contract_symbol ASC
                    """,
                    (sel_date,),
                ).fetchall()
            ]

        rows = []
        for r in raw:
            cl = r["close"]
            pr = r["pr_close"]
            chg = (cl - pr) if (cl is not None and pr is not None) else "N/A"
            rows.append({
                "DATE": r["trade_date"],
                "SYMBOL": r["contract_symbol"],
                "PR_CL": pr if pr is not None else "N/A",
                "OPEN": r["open"] if r["open"] is not None else "N/A",
                "High": r["high"] if r["high"] is not None else "N/A",
                "LOW": r["low"] if r["low"] is not None else "N/A",
                "AVG": r["avg_price"] if r["avg_price"] is not None else "N/A",
                "CLOSE": cl if cl is not None else "N/A",
                "VOLUME": r["volume"] if r["volume"] is not None else "N/A",
                "Change": chg,
            })

        return {
            "view": "date_summary",
            "selected_date": sel_date,
            "rows_count": len(rows),
            "no_data_message": None if rows else "No data available for this date.",
            "message": None if rows else "No data available for this date.",
            "rows": rows,
            "metadata": meta,
        }

    def preview_rolling_window_cleanup(self, months: int = 2) -> Dict[str, Any]:
        res = self.preview_rolling_retention(rolling_months=months)
        return {
            **res,
            "futures_rows_retained_in_active_window": res.get("total_rows_retained", 0),
            "futures_rows_older_than_cutoff": res.get("total_rows_outside_window", 0),
        }

    def preview_rolling_retention(self, rolling_months: int = 2) -> Dict[str, Any]:
        """Preview which months and record counts fall outside the rolling window before pruning."""
        with get_connection(self.db_path) as c:
            max_date = c.execute("SELECT MAX(trade_date) FROM futures_ohlcv").fetchone()[0]
            cutoff = self._get_rolling_cutoff_month(max_date, rolling_months)
            if not cutoff:
                return {"cutoff_date": None, "months_to_archive": [], "rows_affected": 0}
            rows_outside = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT substr(trade_date, 1, 7) AS month, COUNT(*) AS rows_count,
                           MIN(trade_date) AS min_date, MAX(trade_date) AS max_date
                    FROM futures_ohlcv
                    WHERE trade_date < ?
                    GROUP BY substr(trade_date, 1, 7)
                    ORDER BY month ASC
                    """,
                    (cutoff,),
                ).fetchall()
            ]
            rows_retained = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT substr(trade_date, 1, 7) AS month, COUNT(*) AS rows_count,
                           MIN(trade_date) AS min_date, MAX(trade_date) AS max_date
                    FROM futures_ohlcv
                    WHERE trade_date >= ?
                    GROUP BY substr(trade_date, 1, 7)
                    ORDER BY month ASC
                    """,
                    (cutoff,),
                ).fetchall()
            ]
        return {
            "rolling_months": rolling_months,
            "latest_date": max_date,
            "cutoff_date": cutoff,
            "months_outside_active_window": rows_outside,
            "months_retained_in_active_window": rows_retained,
            "total_rows_outside_window": sum(r["rows_count"] for r in rows_outside),
            "total_rows_retained": sum(r["rows_count"] for r in rows_retained),
            "note": "Original source files in data/raw/ and database history are preserved; the rolling window filters active comparison views and exported Futures_Analysis workbooks.",
        }
