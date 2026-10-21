from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from psx_app.database.repository import Repository
from psx_app.database.schema import get_connection


class FuturesService:
    """
    Module C — Futures Comparison and Annualized Analysis Service.
    Provides all 7 logical views matching Futures_Analysis (3).xlsx:
      1. Monthly Comparison (Selected Date + Days, sorted by Annualized % asc)
      2. Month Filter (Selected Date + Days + Month/Contract, sorted by Annualized % asc)
      3. Symbol Filter (ALL Dates for Selected Month/Contract + Symbol + Days, sorted by Date asc)
      4. Annualized Comparison (Selected Date + Days, all symbols & contracts, sorted by Annualized % asc)
      5. Date Filter (Selected Date + Days, full day comparison, sorted by Annualized % asc)
      6. Future Symbol Summary (Symbol/Item across all retained dates, sorted by DATE asc)
      7. Date Summary (Selected Date across all symbols, sorted by SYMBOL asc)
    Enforces strict same-date matching (never forward-filling missing data; returns 'N/A').
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.repo = Repository(db_path)

    def _get_rolling_cutoff_month(self, max_date_str: Optional[str], rolling_months: int = 2) -> Optional[str]:
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

    # ------------------------------------------------------------------
    # Calendar-style free date selection:
    # The user may pick ANY date (calendar input, same as typing a value into the
    # Excel filter cells). If the chosen date is not an available trading day in
    # the active window, resolve to the nearest available trading day <= selected
    # (or the earliest available day if everything is later), and report both the
    # requested and resolved dates so the UI can show exactly what is displayed.
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_selected_date(sel_date: Optional[str], pool_dates: List[str]):
        if not sel_date or sel_date in ("ALL", "ALL_HISTORY"):
            return sel_date, sel_date, False
        try:
            datetime.strptime(sel_date, "%Y-%m-%d")
        except Exception:
            return None, sel_date, True
        pool = sorted(pool_dates or [])
        if sel_date in pool:
            return sel_date, sel_date, False
        le = [d for d in pool if d <= sel_date]
        if le:
            return le[-1], sel_date, True
        return (pool[0] if pool else None), sel_date, True

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

        meta = self.get_metadata(apply_rolling=apply_rolling)
        eff_days = int(days) if (days is not None and int(days) > 0) else meta["default_days"]
        cutoff = meta["cutoff_date"]

        # Defaults matching legacy Futures_Analysis (3).xlsx
        if view_name == "symbol_filter":
            default_contract = "OCTB" if "OCTB" in meta["contracts"] else (meta["contracts"][0] if meta["contracts"] else None)
            sel_contract = contract_month if contract_month else default_contract
            sel_symbol = base_symbol if base_symbol else ("OGDC" if "OGDC" in meta["base_symbols"] else (meta["base_symbols"][0] if meta["base_symbols"] else None))
            # In legacy Excel, Symbol Filter shows ALL retained dates by default unless a specific date is requested
            sel_date = selected_date if selected_date else "ALL"
        else:
            default_contract = "OCT" if "OCT" in meta["contracts"] else (meta["contracts"][0] if meta["contracts"] else None)
            sel_contract = contract_month if contract_month else default_contract
            sel_symbol = base_symbol if base_symbol else ("OGDC" if "OGDC" in meta["base_symbols"] else (meta["base_symbols"][0] if meta["base_symbols"] else None))
            sel_date = selected_date if selected_date else meta["latest_date"]

        if not sel_date and not meta["latest_date"]:
            return {
                "view": view_name,
                "selected_date": None,
                "rows_count": 0,
                "contract_month": sel_contract,
                "base_symbol": sel_symbol,
                "days": eff_days,
                "rows": [],
                "metadata": meta,
            }

        # Resolve any free calendar-picked date to the nearest available trading day
        requested_date = sel_date
        date_was_resolved = False
        if sel_date not in ("ALL", "ALL_HISTORY", None):
            date_pool = meta.get("dates") or meta.get("retained_dates") or []
            sel_date, requested_date, date_was_resolved = self._resolve_selected_date(sel_date, date_pool)

        clauses: List[str] = []
        params: List[Any] = []

        # Date filtering: supports specific YYYY-MM-DD, 'ALL' (retained window), or 'ALL_HISTORY' (entire DB)
        if sel_date == "ALL_HISTORY":
            pass
        elif sel_date == "ALL":
            if cutoff:
                clauses.append("f.trade_date >= ?")
                params.append(cutoff)
        else:
            clauses.append("f.trade_date = ?")
            params.append(sel_date)

        # Contract/Month & Symbol filtering per view
        if view_name == "month_filter":
            if sel_contract and sel_contract != "ALL":
                clauses.append("f.contract_month = ?")
                params.append(sel_contract)
        elif view_name == "symbol_filter":
            if sel_contract and sel_contract != "ALL":
                clauses.append("f.contract_month = ?")
                params.append(sel_contract)
            if sel_symbol and sel_symbol != "ALL":
                clauses.append("f.base_symbol = ?")
                params.append(sel_symbol)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
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
            {where_sql}
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

        # In legacy Excel 'Symbol Filter' across all dates, rows are sorted by Date Ascending (then Annualized % asc)
        if view_name == "symbol_filter" and sel_date in ("ALL", "ALL_HISTORY"):
            rows.sort(key=lambda r: (r["trade_date"], r["_sort_key"], r["symbol"], r["contract"]))
        else:
            # Sort by Annualized % Ascending (lowest first, highest last; N/A at the end)
            rows.sort(key=lambda r: (r["_sort_key"], r["trade_date"], r["symbol"], r["contract"]))

        for r in rows:
            r.pop("_sort_key", None)

        return {
            "view": view_name,
            "selected_date": sel_date,
            "requested_date": requested_date,
            "date_was_resolved": date_was_resolved,
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
            else ("AGHA-OCT" if "AGHA-OCT" in meta["contract_symbols"] else (meta["contract_symbols"][0] if meta["contract_symbols"] else None))
        )
        cutoff = meta["cutoff_date"]

        clauses: List[str] = []
        params: List[Any] = []
        if sel_sym and sel_sym != "ALL":
            clauses.append("contract_symbol = ?")
            params.append(sel_sym)
        if cutoff:
            clauses.append("trade_date >= ?")
            params.append(cutoff)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_connection(self.db_path) as c:
            raw = [
                dict(r)
                for r in c.execute(
                    f"""
                    SELECT trade_date, contract_symbol, pr_close, open, high, low, avg_price, close, volume
                    FROM futures_ohlcv
                    {where_sql}
                    ORDER BY trade_date ASC, contract_symbol ASC
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
        Displays all available symbols and records from 2026F for the exact selected_date (or ALL retained dates),
        sorted by SYMBOL ascending, with Change = CLOSE - PR_CL.
        """
        meta = self.get_metadata(apply_rolling=apply_rolling)
        sel_date = selected_date if selected_date else meta["latest_date"]
        cutoff = meta["cutoff_date"]

        # Resolve any free calendar-picked date to the nearest available trading day
        requested_date = sel_date
        date_was_resolved = False
        if sel_date not in ("ALL", "ALL_HISTORY", None):
            date_pool = meta.get("dates") or meta.get("retained_dates") or []
            sel_date, requested_date, date_was_resolved = self._resolve_selected_date(sel_date, date_pool)

        clauses: List[str] = []
        params: List[Any] = []
        if sel_date == "ALL_HISTORY":
            pass
        elif sel_date == "ALL":
            if cutoff:
                clauses.append("trade_date >= ?")
                params.append(cutoff)
        else:
            clauses.append("trade_date = ?")
            params.append(sel_date)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_connection(self.db_path) as c:
            raw = [
                dict(r)
                for r in c.execute(
                    f"""
                    SELECT trade_date, contract_symbol, pr_close, open, high, low, avg_price, close, volume
                    FROM futures_ohlcv
                    {where_sql}
                    ORDER BY contract_symbol ASC, trade_date ASC
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
            "view": "date_summary",
            "selected_date": sel_date,
            "requested_date": requested_date,
            "date_was_resolved": date_was_resolved,
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
