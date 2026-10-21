from pathlib import Path
from typing import Any, Dict, List, Optional
import openpyxl
from psx_app.config import AUTHORIZED_ACCOUNTS, CORE_36_TICKERS, DRIVE_MIRROR_DIR
from psx_app.database.schema import get_connection
from psx_app.services.account_service import AccountService
from psx_app.services.futures_service import FuturesService
from psx_app.services.technical_service import TechnicalService


class ReconciliationService:
    """
    Layer 9 — Data Quality & Legacy-to-New Reconciliation Engine.
    """

    def __init__(self, db_path: Optional[Path] = None, drive_mirror: Optional[Path] = None):
        self.db_path = db_path
        self.drive_mirror = drive_mirror or DRIVE_MIRROR_DIR
        self.account_service = AccountService(db_path)
        self.futures_service = FuturesService(db_path)
        self.technical_service = TechnicalService(db_path)

    def get_data_quality_report(self) -> Dict[str, Any]:
        with get_connection(self.db_path) as c:
            issues = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT i.*, s.filename AS source_filename_lookup
                    FROM import_issues i
                    LEFT JOIN source_files s ON s.id = i.source_file_id
                    ORDER BY i.id DESC
                    LIMIT 300
                    """
                ).fetchall()
            ]
            revisions = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM source_revisions ORDER BY id DESC LIMIT 100"
                ).fetchall()
            ]

            # Unmatched futures contracts on latest date (futures contract where base_symbol has no cash close on same date)
            latest_fut_date = c.execute("SELECT MAX(trade_date) FROM futures_ohlcv").fetchone()[0]
            unmatched_futures = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT f.trade_date, f.contract_symbol, f.base_symbol, f.contract_month, f.close AS future_close
                    FROM futures_ohlcv f
                    LEFT JOIN equity_ohlcv e
                        ON e.trade_date = f.trade_date AND e.symbol = f.base_symbol
                    WHERE e.close IS NULL
                    ORDER BY f.trade_date DESC, f.contract_symbol ASC
                    LIMIT 200
                    """
                ).fetchall()
            ]

            unmatched_count = c.execute("""SELECT COUNT(*) FROM futures_ohlcv f LEFT JOIN equity_ohlcv e
                ON e.trade_date=f.trade_date AND e.symbol=f.base_symbol WHERE e.close IS NULL""").fetchone()[0]
            history_range = c.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM equity_ohlcv").fetchone()
            # Insufficient indicator history across 531 tickers
            insufficient_tickers = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT symbol, COUNT(*) AS bars_count, MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
                    FROM equity_ohlcv
                    GROUP BY symbol
                    HAVING COUNT(*) < 200
                    ORDER BY bars_count ASC, symbol ASC
                    """
                ).fetchall()
            ]
            strict_under_26 = [r for r in insufficient_tickers if r["bars_count"] < 26]
            under_200_ema = [r for r in insufficient_tickers if r["bars_count"] < 200]

            # Account checks
            acc_reconciliations = {}
            for acc in AUTHORIZED_ACCOUNTS:
                rep = self.account_service.get_account_report(acc)
                acc_reconciliations[acc] = rep["data_checks"]["reconciliation"]

        return {
            "latest_futures_date": latest_fut_date,
            "import_issues": issues,
            "source_revisions": revisions,
            "unmatched_futures_contracts": {
                "count": unmatched_count,
                "display_limit": 50,
                "items": unmatched_futures[:50],
            },
            "indicator_history_checks": {
                "tickers_under_26_bars_count": len(strict_under_26),
                "tickers_under_26_bars": strict_under_26[:50],
                "tickers_under_200_bars_for_ema200_count": len(under_200_ema),
                "note": f"Cash coverage: {history_range[0] or 'no data'} to {history_range[1] or 'no data'}; {history_range[2]} distinct sessions. Strict EMA-200 requires at least 200 bars per symbol.",
            },
            "account_reconciliations": acc_reconciliations,
        }

    def reconcile_against_legacy_workbooks(self) -> Dict[str, Any]:
        """
        Compare recalculated values in our SQLite database against the 5 legacy Output workbooks
        in drive_mirror/Output folder.
        """
        out_dir = self.drive_mirror / "Output folder"
        results: Dict[str, Any] = {key: {"status": "NOT_CHECKED", "checked_rows": 0,
            "reason": "Historical reference workbook is not installed. No parity claim is made."}
            for key in ("module_a_top5", "module_b_account_91404", "module_b_account_91269", "module_c_futures", "module_d_technical_atrl") }

        # 1. Module A: Top 5 Volume & Rate on 2026-10-16 (raw TXT vs legacy workbook)
        top5_xlsx = out_dir / "PSX_Top5_Volume_Rate_12-08-2026_to_16-10-2026 (1).xlsx"
        if top5_xlsx.exists():
            wb = openpyxl.load_workbook(top5_xlsx, read_only=True, data_only=True)
            mismatches = []
            checked = 0
            with get_connection(self.db_path) as c:
                db_map = {
                    (r["trade_date"], r["ticker"], r["rank"]): (r["rate"], r["volume"], r["trades"])
                    for r in c.execute(
                        "SELECT trade_date, ticker, rank, rate, volume, trades FROM top5_volume_records WHERE trade_date = '2026-10-16'"
                    ).fetchall()
                }
            for s in wb.sheetnames:
                ws = wb[s]
                in_1016 = False
                for row in ws.iter_rows(values_only=True):
                    if not row or row[0] is None:
                        continue
                    if isinstance(row[0], str) and "Top 5 Volume Trades" in row[0]:
                        in_1016 = "(10/16/2026)" in row[0]
                    elif in_1016 and isinstance(row[0], (int, float)) and 1 <= int(row[0]) <= 5:
                        rk = int(row[0])
                        leg_tuple = (float(row[1]), int(round(float(row[2]))), int(round(float(row[3]))))
                        db_tuple = db_map.get(("2026-10-16", s.upper(), rk))
                        checked += 1
                        if db_tuple != leg_tuple:
                            mismatches.append({"ticker": s, "rank": rk, "legacy": leg_tuple, "new": db_tuple})
            wb.close()
            results["module_a_top5"] = {
                "status": ("MATCH" if not mismatches else "DISCREPANCY") if checked else "NOT_CHECKED",
                "scope": "Historical reference rows dated 16-10-2026 only; not the entire database",
                "checked_rows": checked,
                "checked_16_oct_rows": checked,
                "mismatches_count": len(mismatches),
                "mismatches": mismatches,
            }

        # 2. Module B: Account 91404 & Account 91269 YTD & 16-Oct-2026 totals
        for acc, fn in [
            ("91404", "Trade_Summary_Account_91404_Updated_2026-10-16.xlsx"),
            ("91269", "Trade_Summary_Account_91269_Updated_2026-10-15.xlsx"),
        ]:
            p = out_dir / fn
            if p.exists():
                wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
                ws_yr = wb["Yearly Summary"]
                leg_yr_row = None
                for row in ws_yr.iter_rows(min_row=5, max_row=7, values_only=True):
                    if row and row[0] == 2026:
                        leg_yr_row = row
                        break
                wb.close()
                rep = self.account_service.get_account_report(acc)
                cutoff = "2026-10-16" if acc == "91404" else "2026-10-15"
                with get_connection(self.db_path) as conn:
                    fields = ["buy_value", "sell_value", "gross_pnl", "commission_amount", "sst_amount", "net_pnl"]
                    row = conn.execute("SELECT " + ",".join("COALESCE(SUM(" + f + "),0)" for f in fields) +
                        " FROM account_daily_symbol_summary WHERE account_id=? AND trade_date BETWEEN ? AND ?",
                        (acc, "2026-01-01", cutoff)).fetchone()
                    ytd = dict(zip(fields, row))
                if leg_yr_row:
                    leg_buy_val = float(leg_yr_row[2])
                    leg_sell_val = float(leg_yr_row[5])
                    leg_gross = float(leg_yr_row[9])
                    leg_comm = float(leg_yr_row[11])
                    leg_sst = float(leg_yr_row[12])
                    leg_net = float(leg_yr_row[14])
                    diff_net = abs(ytd["net_pnl"] - leg_net)
                    results[f"module_b_account_{acc}"] = {
                        "status": "MATCH" if all(abs(a-b) < 0.01 for a,b in zip(
                            [ytd[f] for f in fields], [leg_buy_val, leg_sell_val, leg_gross, leg_comm, leg_sst, leg_net])) else "DISCREPANCY",
                        "scope": f"Account {acc} totals 01-01-2026 through {cutoff}; 6 financial fields",
                        "checked_rows": 1, "checked_fields": 6,
                        "legacy_ytd_buy_value": leg_buy_val,
                        "new_ytd_buy_value": ytd["buy_value"],
                        "legacy_ytd_sell_value": leg_sell_val,
                        "new_ytd_sell_value": ytd["sell_value"],
                        "legacy_ytd_gross_pnl": leg_gross,
                        "new_ytd_gross_pnl": ytd["gross_pnl"],
                        "legacy_ytd_commission": leg_comm,
                        "new_ytd_commission": ytd["commission_amount"],
                        "legacy_ytd_sst": leg_sst,
                        "new_ytd_sst": ytd["sst_amount"],
                        "legacy_ytd_net_pnl": leg_net,
                        "new_ytd_net_pnl": ytd["net_pnl"],
                        "net_pnl_abs_diff": diff_net,
                    }

        # 3. Module C: Futures Analysis on 2026-10-16 (Days=30)
        fut_xlsx = out_dir / "Futures_Analysis (3).xlsx"
        if fut_xlsx.exists():
            wb = openpyxl.load_workbook(fut_xlsx, read_only=True, data_only=True)
            from datetime import datetime
            comparisons, mismatches = 0, []
            for tab, sheet in [("monthly_comparison", "Monthly Comparison"), ("month_filter", "Month Filter"),
                               ("symbol_filter", "Symbol Filter"), ("annualized_comparison", "Annualized Comparison"), ("date_filter", "Date Filter")]:
                if sheet not in wb.sheetnames: continue
                ws = wb[sheet]
                requested = ws["C4"].value
                contract = requested if tab == "symbol_filter" else (ws["I4"].value if tab == "month_filter" else None)
                symbol = ws["I4"].value if tab == "symbol_filter" else None
                if tab == "symbol_filter": requested = "ALL"
                elif isinstance(requested, datetime): requested = requested.date().isoformat()
                elif isinstance(requested, str):
                    try: requested = datetime.strptime(requested[:10], "%d-%m-%Y").date().isoformat()
                    except ValueError:
                        try: datetime.strptime(requested[:10], "%Y-%m-%d"); requested = requested[:10]
                        except ValueError: requested = "2026-10-16"
                else: requested = "2026-10-16"
                comp = self.futures_service.get_comparison_rows(tab, selected_date=requested, contract_month=contract,
                    base_symbol=symbol, days=int(ws["F4"].value or 30), apply_rolling=False)
                new_map = {(r["trade_date"], r["symbol"], r["contract"]): r for r in comp["rows"]}
                columns = ["current_value", "future_value", "volume", "high", "low", "difference", "difference_pct", "days", "annualized_pct"]
                for row in ws.iter_rows(min_row=7, values_only=True):
                    if not row or not row[1] or not row[2] or row[0] is None: continue
                    d = row[0].date().isoformat() if isinstance(row[0], datetime) else str(row[0])[:10]
                    if len(d)==10 and d[2] == '-':
                        d = datetime.strptime(d, "%d-%m-%Y").date().isoformat()
                    actual = new_map.get((d, str(row[1]), str(row[2])))
                    comparisons += 1
                    bad = []
                    for idx, name in enumerate(columns, start=3):
                        expected = row[idx]
                        if idx in (9, 11) and isinstance(expected, (int,float)): expected *= 100
                        value = actual.get(name) if actual else None
                        if isinstance(expected, (int,float)) and isinstance(value, (int,float)):
                            if abs(expected-value) > 0.001: bad.append(name)
                        elif expected != value and not (expected in (None,"N/A") and value in (None,"N/A")):
                            bad.append(name)
                    if bad: mismatches.append({"sheet": sheet, "date": d, "symbol": row[1], "contract": row[2], "fields": bad})
            wb.close()
            results["module_c_futures"] = {"status": ("MATCH" if not mismatches else "DISCREPANCY") if comparisons else "NOT_CHECKED",
                "scope": "All populated reference rows across five comparison sheets; same-date cash joins; historical fixture coverage only",
                "checked_rows": comparisons, "checked_fields_per_row": 9, "mismatches_count": len(mismatches), "mismatches": mismatches[:100]}

        # 4. Module D: Technical Analysis ATRL on 2026-10-16
        rsi_xlsx = out_dir / "PSX_RSI_Pivot_Analysis (4).xlsx"
        if rsi_xlsx.exists():
            wb = openpyxl.load_workbook(rsi_xlsx, read_only=True, data_only=True)
            ws_ad = wb["ATRL_DATA"]
            last_r = None
            for row in ws_ad.iter_rows(min_row=2, values_only=True):
                if row and row[0]:
                    last_r = row
            wb.close()
            from datetime import datetime
            cutoff = last_r[0].date().isoformat() if last_r and isinstance(last_r[0], datetime) else str(last_r[0])[:10] if last_r else None
            with get_connection(self.db_path) as conn:
                bars = [dict(r) for r in conn.execute("SELECT * FROM equity_ohlcv WHERE symbol=? AND trade_date <= ? ORDER BY trade_date", ("ATRL", cutoff))]
            atrl_new = self.technical_service.calculate_series_for_bars("ATRL", bars)["latest"] if bars else None
            if last_r and atrl_new:
                results["module_d_technical_atrl"] = {
                    "status": "NOT_CHECKED",
                    "date": cutoff,
                    "scope": "ATRL reference close and 13 indicators at the same historical date",
                    "checked_rows": 1,
                    "legacy": {
                        "close": float(last_r[4]),
                        "rsi14": float(last_r[6]),
                        "macd": float(last_r[7]),
                        "macd_sig": float(last_r[8]),
                        "macd_hist": float(last_r[9]),
                        "bb_up": float(last_r[10]),
                        "bb_mid": float(last_r[11]),
                        "bb_low": float(last_r[12]),
                        "ema9": float(last_r[15]),
                        "ema21": float(last_r[16]),
                        "ema50": float(last_r[17]),
                        "ema200_recursive": float(last_r[18]),
                        "adx14": float(last_r[20]),
                    },
                    "new": {
                        "close": round(atrl_new["close"], 2),
                        "rsi14": round(atrl_new["rsi14"], 2),
                        "macd": round(atrl_new["macd"], 2),
                        "macd_sig": round(atrl_new["macd_sig"], 2),
                        "macd_hist": round(atrl_new["macd_hist"], 2),
                        "bb_up": round(atrl_new["bb_up"], 2),
                        "bb_mid": round(atrl_new["bb_mid"], 2),
                        "bb_low": round(atrl_new["bb_low"], 2),
                        "ema9": round(atrl_new["ema9"], 2),
                        "ema21": round(atrl_new["ema21"], 2),
                        "ema50": round(atrl_new["ema50"], 2),
                        "ema200_recursive": round(atrl_new["ema200_recursive"], 2),
                        "ema200_strict": atrl_new["ema200"],
                        "adx14": round(atrl_new["adx14"], 2),
                    },
                }

        technical = results["module_d_technical_atrl"]
        if technical.get("legacy") and technical.get("new"):
            bad = [key for key, value in technical["legacy"].items()
                   if technical["new"].get(key) is None or abs(value-technical["new"][key]) > 0.011]
            technical["mismatches"] = bad
            technical["checked_fields"] = len(technical["legacy"])
            technical["status"] = "DISCREPANCY" if bad else "MATCH"
        return results
