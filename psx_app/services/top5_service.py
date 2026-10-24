from psx_app.services.result_cache import persisted_result
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import TOP5_DEFAULT_TICKERS
from psx_app.database.schema import get_connection
from psx_app.parsers.top5_parser import normalize_ticker


class Top5Service:
    """Module A — Daily Top 5 Volume and Rate Register Service."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    @persisted_result
    def get_metadata(self) -> Dict[str, Any]:
        with get_connection(self.db_path) as c:
            dates = [
                r[0]
                for r in c.execute(
                    "SELECT DISTINCT trade_date FROM top5_volume_records ORDER BY trade_date DESC"
                ).fetchall()
            ]
            tickers = [
                r[0]
                for r in c.execute(
                    "SELECT DISTINCT ticker FROM top5_volume_records ORDER BY ticker ASC"
                ).fetchall()
            ]
            total_rows = c.execute("SELECT COUNT(*) FROM top5_volume_records").fetchone()[0]
        return {
            "available_dates": dates,
            "latest_date": dates[0] if dates else None,
            "available_tickers": tickers or TOP5_DEFAULT_TICKERS,
            "total_records": total_rows,
        }

    @persisted_result
    def get_register(
        self,
        ticker: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        meta = self.get_metadata()
        sel_ticker = normalize_ticker(ticker) if ticker and ticker != "ALL" else None
        clauses: List[str] = []
        params: List[Any] = []

        if sel_ticker:
            clauses.append("ticker = ?")
            params.append(sel_ticker)
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)
        if search:
            q = f"%{search.strip().upper()}%"
            clauses.append("(ticker LIKE ? OR trade_date LIKE ?)")
            params.extend([q, q])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT trade_date, ticker, rank, rate, volume, trades,
                   snapshot_time, source_filename, origin_type
            FROM top5_volume_records
            {where_sql}
            ORDER BY trade_date DESC, ticker ASC, rank ASC
        """
        with get_connection(self.db_path) as c:
            rows = [dict(r) for r in c.execute(sql, params).fetchall()]

        blocks_map: Dict[str, Dict[str, Any]] = {}
        block_order: List[str] = []
        for r in rows:
            key = f"{r['ticker']}|{r['trade_date']}"
            if key not in blocks_map:
                mmddyyyy = datetime.strptime(r["trade_date"], "%Y-%m-%d").strftime("%m/%d/%Y")
                ddmmyyyy = datetime.strptime(r["trade_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
                blocks_map[key] = {
                    "ticker": r["ticker"],
                    "trade_date": r["trade_date"],
                    "mmddyyyy": mmddyyyy,
                    "title": f"{r['ticker']} — Top 5 Volume Trades ({ddmmyyyy})",
                    "max_volume": 0,
                    "rows": [],
                }
                block_order.append(key)
            blk = blocks_map[key]
            blk["rows"].append(r)
            if r["volume"] > blk["max_volume"]:
                blk["max_volume"] = r["volume"]

        date_blocks = [blocks_map[k] for k in block_order]
        return {
            "available_tickers": meta["available_tickers"],
            "available_dates": meta["available_dates"],
            "latest_date": meta["latest_date"],
            "blocks_count": len(date_blocks),
            "total_rows": len(rows),
            "date_blocks": date_blocks,
        }

    @persisted_result
    def get_ticker_trend(self, ticker: str) -> Dict[str, Any]:
        norm = normalize_ticker(ticker)
        with get_connection(self.db_path) as c:
            rows = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT trade_date,
                           MAX(CASE WHEN rank = 1 THEN rate END) AS rank1_rate,
                           MAX(CASE WHEN rank = 1 THEN volume END) AS rank1_volume,
                           SUM(volume) AS top5_total_volume,
                           SUM(trades) AS top5_total_trades
                    FROM top5_volume_records
                    WHERE ticker = ?
                    GROUP BY trade_date
                    ORDER BY trade_date ASC
                    """,
                    (norm,),
                ).fetchall()
            ]
        for r in rows:
            r["mmddyyyy"] = datetime.strptime(r["trade_date"], "%Y-%m-%d").strftime("%m/%d/%Y")
        return {
            "ticker": norm,
            "trading_days": len(rows),
            "trend": rows,
        }
