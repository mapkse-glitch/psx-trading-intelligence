from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import AUTHORIZED_ACCOUNTS, DEFAULT_SETTINGS
from psx_app.database.repository import Repository
from psx_app.database.schema import get_connection


class AccountService:
    """
    Module B — Multi-Account Trading, Profit & Performance Management Service.
    Enforces strict separation between Account 91404 and Account 91269.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.repo = Repository(db_path)

    def recalculate_account_date_from_executions(
        self,
        account_id: str,
        trade_date: str,
        batch_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recalculate symbol-level summary rows for (account_id, trade_date) from raw trade_executions.
        """
        settings = self.repo.get_settings()
        slab2_start = float(settings.get("commission_slab2_start", 54.0))
        now = datetime.now(timezone.utc).isoformat()

        with get_connection(self.db_path) as c:
            execs = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT * FROM trade_executions
                    WHERE account_id = ? AND trade_date = ?
                    ORDER BY id ASC
                    """,
                    (account_id, trade_date),
                ).fetchall()
            ]
            if not execs:
                return []

            by_sym: Dict[str, List[Dict[str, Any]]] = {}
            for ex in execs:
                by_sym.setdefault(ex["symbol"], []).append(ex)

            results: List[Dict[str, Any]] = []
            for sym in sorted(by_sym.keys()):
                rows = by_sym[sym]
                buy_qty = sum(r["quantity"] for r in rows if r["normalized_side"] == "BUY")
                buy_val = float(sum(Decimal(str(r["trade_value"])) for r in rows if r["normalized_side"] == "BUY"))
                sell_qty = sum(r["quantity"] for r in rows if r["normalized_side"] == "SELL")
                sell_val = float(sum(Decimal(str(r["trade_value"])) for r in rows if r["normalized_side"] == "SELL"))

                avg_buy = (buy_val / buy_qty) if buy_qty > 0 else None
                avg_sell = (sell_val / sell_qty) if sell_qty > 0 else None
                price_diff = (avg_sell - avg_buy) if (avg_buy is not None and avg_sell is not None) else None
                net_qty = buy_qty - sell_qty
                gross_pnl = float(Decimal(str(sell_val)) - Decimal(str(buy_val)))

                comm = float(sum(Decimal(str(r["commission_amount"])) for r in rows if r["normalized_side"] == "SELL"))
                sst = float(sum(Decimal(str(r["sst_amount"])) for r in rows if r["normalized_side"] == "SELL"))
                total_charges = float(Decimal(str(comm)) + Decimal(str(sst)))
                net_pnl = float(Decimal(str(gross_pnl)) - Decimal(str(total_charges)))
                rob = (net_pnl / buy_val) if buy_val > 0 else None

                sell_slabs = {r["commission_slab"] for r in rows if r["normalized_side"] == "SELL" and r.get("commission_slab")}
                if sell_qty == 0:
                    slab_label = "—"
                elif len(sell_slabs) == 1:
                    slab_label = next(iter(sell_slabs))
                elif len(sell_slabs) > 1:
                    slab_label = "Mixed slabs (execution-level)"
                else:
                    slab_label = "0.0325% of sell value" if (avg_sell or 0) >= slab2_start else "0.0175 paisa per share"

                mkt = rows[0].get("market_type") or ("FUT" if "-" in sym else "Reg")
                src_fn = rows[-1].get("source_filename") or "TradeLog"

                c.execute(
                    """
                    INSERT INTO account_daily_symbol_summary (
                        account_id, trade_date, symbol, market_type,
                        buy_qty, buy_value, avg_buy_price,
                        sell_qty, sell_value, avg_sell_price,
                        price_diff, net_qty, gross_pnl,
                        commission_slab_label, commission_amount, sst_amount,
                        total_charges, net_pnl, return_on_buy,
                        origin_type, source_filename, batch_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RAW_EXECUTIONS', ?, ?, ?)
                    ON CONFLICT(account_id, trade_date, symbol) DO UPDATE SET
                        market_type = excluded.market_type,
                        buy_qty = excluded.buy_qty,
                        buy_value = excluded.buy_value,
                        avg_buy_price = excluded.avg_buy_price,
                        sell_qty = excluded.sell_qty,
                        sell_value = excluded.sell_value,
                        avg_sell_price = excluded.avg_sell_price,
                        price_diff = excluded.price_diff,
                        net_qty = excluded.net_qty,
                        gross_pnl = excluded.gross_pnl,
                        commission_slab_label = excluded.commission_slab_label,
                        commission_amount = excluded.commission_amount,
                        sst_amount = excluded.sst_amount,
                        total_charges = excluded.total_charges,
                        net_pnl = excluded.net_pnl,
                        return_on_buy = excluded.return_on_buy,
                        origin_type = 'RAW_EXECUTIONS',
                        source_filename = excluded.source_filename,
                        batch_id = excluded.batch_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        account_id, trade_date, sym, mkt,
                        buy_qty, buy_val, avg_buy,
                        sell_qty, sell_val, avg_sell,
                        price_diff, net_qty, gross_pnl,
                        slab_label, comm, sst,
                        total_charges, net_pnl, rob,
                        src_fn, batch_id, now,
                    ),
                )
                results.append({
                    "account_id": account_id,
                    "trade_date": trade_date,
                    "symbol": sym,
                    "buy_qty": buy_qty,
                    "buy_value": buy_val,
                    "avg_buy_price": avg_buy,
                    "sell_qty": sell_qty,
                    "sell_value": sell_val,
                    "avg_sell_price": avg_sell,
                    "price_diff": price_diff,
                    "net_qty": net_qty,
                    "gross_pnl": gross_pnl,
                    "commission_slab_label": slab_label,
                    "commission_amount": comm,
                    "sst_amount": sst,
                    "total_charges": total_charges,
                    "net_pnl": net_pnl,
                    "return_on_buy": rob,
                })
            c.commit()
        return results

    @staticmethod
    def _aggregate_rows(rows: List[Dict[str, Any]], label_key: str, label_val: Any, slab2_start: float = 54.0) -> Dict[str, Any]:
        b_qty = sum(int(r["buy_qty"]) for r in rows)
        s_qty = sum(int(r["sell_qty"]) for r in rows)
        b_val = float(sum(Decimal(str(r["buy_value"])) for r in rows))
        s_val = float(sum(Decimal(str(r["sell_value"])) for r in rows))
        avg_b = (b_val / b_qty) if b_qty > 0 else None
        avg_s = (s_val / s_qty) if s_qty > 0 else None
        p_diff = (avg_s - avg_b) if (avg_b is not None and avg_s is not None) else None
        net_q = b_qty - s_qty
        gross = float(Decimal(str(s_val)) - Decimal(str(b_val)))
        comm = float(sum(Decimal(str(r["commission_amount"])) for r in rows))
        sst = float(sum(Decimal(str(r["sst_amount"])) for r in rows))
        t_chg = float(Decimal(str(comm)) + Decimal(str(sst)))
        net_p = float(Decimal(str(gross)) - Decimal(str(t_chg)))
        rob = (net_p / b_val) if b_val > 0 else None

        slab_label = "—"
        if s_qty > 0 and avg_s is not None:
            slab_label = "0.0325% of sell value" if avg_s >= slab2_start else "0.0175 paisa per share"

        syms_list = sorted({r["symbol"] for r in rows if r.get("symbol")})
        dates_list = sorted({r["trade_date"] for r in rows if r.get("trade_date")})
        if len(dates_list) == 1:
            dates_display = dates_list[0]
        elif len(dates_list) > 1:
            dates_display = f"{dates_list[0]} → {dates_list[-1]} ({len(dates_list)}d)"
        else:
            dates_display = "—"

        return {
            label_key: label_val,
            "trading_days": len(dates_list),
            "dates_list": dates_list,
            "dates_str": ", ".join(dates_list),
            "dates_display": dates_display,
            "first_date": dates_list[0] if dates_list else None,
            "last_date": dates_list[-1] if dates_list else None,
            "symbols_list": syms_list,
            "symbols_count": len(syms_list),
            "symbols_str": ", ".join(syms_list),
            "buy_qty": b_qty,
            "buy_value": b_val,
            "avg_buy_price": avg_b,
            "sell_qty": s_qty,
            "sell_value": s_val,
            "avg_sell_price": avg_s,
            "price_diff": p_diff,
            "net_qty": net_q,
            "gross_pnl": gross,
            "commission_slab_label": slab_label,
            "commission_amount": comm,
            "sst_amount": sst,
            "total_charges": t_chg,
            "net_pnl": net_p,
            "return_on_buy": rob,
            "note": "",
        }

    def get_account_report(self, account_id: str, selected_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Return full isolated report for a single account (91404 or 91269):
        Dashboard, Daily Summary, Daily Detail by Date, MTD, QTD, YTD, Monthly Summary,
        Yearly Summary, Symbol Performance, Trade Log, Settings, Data Checks, Import Audit.
        """
        if account_id not in AUTHORIZED_ACCOUNTS:
            raise ValueError(f"Unauthorized or unknown account '{account_id}'.")

        settings = self.repo.get_settings()
        slab2_start = float(settings.get("commission_slab2_start", 54.0))

        with get_connection(self.db_path) as c:
            sym_rows = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT * FROM account_daily_symbol_summary
                    WHERE account_id = ?
                    ORDER BY trade_date ASC, symbol ASC
                    """,
                    (account_id,),
                ).fetchall()
            ]
            exec_rows = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT * FROM trade_executions
                    WHERE account_id = ?
                    ORDER BY trade_date DESC, trade_time DESC, id DESC
                    LIMIT 1000
                    """,
                    (account_id,),
                ).fetchall()
            ]
            issues = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT * FROM import_issues
                    WHERE module = 'MODULE_B' AND (account_id = ? OR account_id IS NULL OR issue_type = 'UNEXPECTED_ACCOUNT')
                    ORDER BY id DESC
                    LIMIT 200
                    """,
                    (account_id,),
                ).fetchall()
            ]

        by_date: Dict[str, List[Dict[str, Any]]] = {}
        by_month: Dict[str, List[Dict[str, Any]]] = {}
        by_year: Dict[str, List[Dict[str, Any]]] = {}
        by_symbol: Dict[str, List[Dict[str, Any]]] = {}

        for r in sym_rows:
            d = r["trade_date"]
            m = d[:7]  # YYYY-MM
            y = d[:4]  # YYYY
            by_date.setdefault(d, []).append(r)
            by_month.setdefault(m, []).append(r)
            by_year.setdefault(y, []).append(r)
            by_symbol.setdefault(r["symbol"], []).append(r)

        available_dates = sorted(by_date.keys())
        latest_date = available_dates[-1] if available_dates else None
        active_date = selected_date if (selected_date and selected_date in by_date) else latest_date

        daily_summary = [
            self._aggregate_rows(by_date[d], "trade_date", d, slab2_start)
            for d in available_dates
        ]
        daily_total = self._aggregate_rows(sym_rows, "trade_date", "TOTAL", slab2_start) if sym_rows else None

        monthly_summary = [
            self._aggregate_rows(by_month[m], "month", f"{m}-01", slab2_start)
            for m in sorted(by_month.keys())
        ]
        monthly_total = self._aggregate_rows(sym_rows, "month", "TOTAL", slab2_start) if sym_rows else None

        yearly_summary = [
            self._aggregate_rows(by_year[y], "year", int(y), slab2_start)
            for y in sorted(by_year.keys())
        ]
        yearly_total = self._aggregate_rows(sym_rows, "year", "TOTAL", slab2_start) if sym_rows else None

        # MTD, QTD, YTD based on latest_date in that account
        mtd_rows: List[Dict[str, Any]] = []
        qtd_rows: List[Dict[str, Any]] = []
        ytd_rows: List[Dict[str, Any]] = []
        mtd_period = {"start": None, "end": latest_date, "trading_days": 0}
        qtd_period = {"start": None, "end": latest_date, "trading_days": 0, "quarter_label": None}
        ytd_period = {"start": None, "end": latest_date, "trading_days": 0}

        if latest_date:
            dt_latest = datetime.strptime(latest_date, "%Y-%m-%d")
            mtd_start = f"{dt_latest.year:04d}-{dt_latest.month:02d}-01"
            q_num = (dt_latest.month - 1) // 3 + 1
            q_start_month = (q_num - 1) * 3 + 1
            qtd_start = f"{dt_latest.year:04d}-{q_start_month:02d}-01"
            ytd_start = f"{dt_latest.year:04d}-01-01"

            mtd_rows = [r for r in sym_rows if mtd_start <= r["trade_date"] <= latest_date]
            qtd_rows = [r for r in sym_rows if qtd_start <= r["trade_date"] <= latest_date]
            ytd_rows = [r for r in sym_rows if ytd_start <= r["trade_date"] <= latest_date]

            mtd_days = sorted({r["trade_date"] for r in mtd_rows})
            qtd_days = sorted({r["trade_date"] for r in qtd_rows})
            ytd_days = sorted({r["trade_date"] for r in ytd_rows})

            mtd_period = {
                "start": mtd_start,
                "end": latest_date,
                "first_trading_day": mtd_days[0] if mtd_days else None,
                "trading_days": len(mtd_days),
                "daily_rows": [self._aggregate_rows(by_date[d], "trade_date", d, slab2_start) for d in mtd_days],
            }
            qtd_period = {
                "start": qtd_start,
                "end": latest_date,
                "first_trading_day": qtd_days[0] if qtd_days else None,
                "trading_days": len(qtd_days),
                "quarter_label": f"Q{q_num} {dt_latest.year}",
                "daily_rows": [self._aggregate_rows(by_date[d], "trade_date", d, slab2_start) for d in qtd_days],
            }
            ytd_period = {
                "start": ytd_start,
                "end": latest_date,
                "first_trading_day": ytd_days[0] if ytd_days else None,
                "trading_days": len(ytd_days),
                "daily_rows": [self._aggregate_rows(by_date[d], "trade_date", d, slab2_start) for d in ytd_days],
            }

        mtd_summary = self._aggregate_rows(mtd_rows, "period", "MTD", slab2_start)
        qtd_summary = self._aggregate_rows(qtd_rows, "period", "QTD", slab2_start)
        ytd_summary = self._aggregate_rows(ytd_rows, "period", "YTD", slab2_start)

        # Symbol performance across all dates sorted by Net P&L DESC
        symbol_performance = [
            self._aggregate_rows(by_symbol[s], "symbol", s, slab2_start)
            for s in by_symbol.keys()
        ]
        symbol_performance.sort(key=lambda x: x["net_pnl"], reverse=True)
        if symbol_performance:
            symbol_performance[0]["note"] = "◄ Best performer"
            if len(symbol_performance) > 1:
                symbol_performance[-1]["note"] = "◄ Worst performer"
        symbol_performance_total = self._aggregate_rows(sym_rows, "symbol", "TOTAL", slab2_start) if sym_rows else None
        best_symbol = symbol_performance[0] if symbol_performance else None
        worst_symbol = symbol_performance[-1] if symbol_performance else None

        latest_day_summary = (
            self._aggregate_rows(by_date[latest_date], "trade_date", latest_date, slab2_start)
            if latest_date
            else None
        )
        active_day_detail = {
            "trade_date": active_date,
            "summary": self._aggregate_rows(by_date[active_date], "trade_date", active_date, slab2_start) if active_date else None,
            "symbols": by_date.get(active_date, []) if active_date else [],
        }

        # Reconciliation & Data Checks
        reconciliation_checks = self._run_account_reconciliation(
            account_id, sym_rows, daily_summary, monthly_summary, yearly_summary, ytd_summary
        )

        total_traded_volume_pkr = (
            float(Decimal(str(ytd_summary["buy_value"])) + Decimal(str(ytd_summary["sell_value"])))
            if ytd_summary
            else 0.0
        )
        total_traded_shares = (
            int(ytd_summary["buy_qty"] + ytd_summary["sell_qty"])
            if ytd_summary
            else 0
        )

        dashboard = {
            "account_id": account_id,
            "latest_trading_day": latest_date,
            "latest_day": latest_day_summary,
            "mtd": mtd_summary,
            "qtd": qtd_summary,
            "ytd": ytd_summary,
            "total_traded_turnover_pkr": total_traded_volume_pkr,
            "total_traded_shares": total_traded_shares,
            "symbols_count": len(by_symbol),
            "trading_days_count": len(available_dates),
            "best_symbol": best_symbol,
            "worst_symbol": worst_symbol,
        }

        return {
            "account_id": account_id,
            "available_dates": available_dates,
            "trading_dates": available_dates,
            "available_symbols": sorted(by_symbol.keys()),
            "selected_date": active_date,
            "dashboard": dashboard,
            "daily_summary": {"rows": daily_summary, "total": daily_total},
            "all_daily_symbol_rows": sym_rows,
            "daily_detail": active_day_detail,
            "selected_date_detail": active_day_detail,
            "all_daily_blocks": {
                d: {
                    "summary": self._aggregate_rows(by_date[d], "trade_date", d, slab2_start),
                    "symbols": by_date[d],
                }
                for d in available_dates
            },
            "mtd_summary": {**mtd_summary, **mtd_period},
            "qtd_summary": {**qtd_summary, **qtd_period},
            "ytd_summary": {**ytd_summary, **ytd_period},
            "monthly_summary": {"rows": monthly_summary, "total": monthly_total},
            "yearly_summary": {"rows": yearly_summary, "total": yearly_total},
            "symbol_performance": symbol_performance,
            "symbol_performance_total": symbol_performance_total,
            "trade_log": exec_rows,
            "data_checks": {
                "reconciliation": reconciliation_checks,
                "issues": issues,
            },
            "settings": {
                "account_id": account_id,
                "commission_slab1_upper": settings["commission_slab1_upper"],
                "commission_slab1_paisa_per_share": settings["commission_slab1_paisa_per_share"],
                "commission_slab2_start": settings["commission_slab2_start"],
                "commission_slab2_rate": settings["commission_slab2_rate"],
                "sst_rate": settings["sst_rate"],
                "currency": settings["currency"],
            },
        }

    def _run_account_reconciliation(
        self,
        account_id: str,
        sym_rows: List[Dict[str, Any]],
        daily_summary: List[Dict[str, Any]],
        monthly_summary: List[Dict[str, Any]],
        yearly_summary: List[Dict[str, Any]],
        ytd_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        sum_daily_net = sum(Decimal(str(r["net_pnl"])) for r in daily_summary)
        sum_monthly_net = sum(Decimal(str(r["net_pnl"])) for r in monthly_summary)
        sum_yearly_net = sum(Decimal(str(r["net_pnl"])) for r in yearly_summary)
        sum_sym_net = sum(Decimal(str(r["net_pnl"])) for r in sym_rows)

        unmatched_positions = [
            {"trade_date": r["trade_date"], "symbol": r["symbol"], "net_qty": r["net_qty"]}
            for r in sym_rows
            if r["net_qty"] != 0
        ]

        diff_daily_vs_sym = float(abs(sum_daily_net - sum_sym_net))
        diff_monthly_vs_daily = float(abs(sum_monthly_net - sum_daily_net))
        diff_yearly_vs_daily = float(abs(sum_yearly_net - sum_daily_net))

        passed = (
            diff_daily_vs_sym < 0.01
            and diff_monthly_vs_daily < 0.01
            and diff_yearly_vs_daily < 0.01
        )
        return {
            "account_id": account_id,
            "passed": passed,
            "daily_vs_symbol_net_pnl_diff": diff_daily_vs_sym,
            "monthly_vs_daily_net_pnl_diff": diff_monthly_vs_daily,
            "yearly_vs_daily_net_pnl_diff": diff_yearly_vs_daily,
            "unmatched_net_quantity_rows": unmatched_positions,
            "unmatched_count": len(unmatched_positions),
        }
