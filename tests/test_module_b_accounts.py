from pathlib import Path
import pytest
from psx_app.config import DEFAULT_SETTINGS
from psx_app.parsers.tradelog_parser import compute_execution_charges, parse_tradelog_content
from psx_app.services.account_service import AccountService


def test_commission_slab1_slab2_boundary_and_sst():
    # Slab 1: Sell price < 54.00 PKR -> 0.0175 paisa/share = qty * 0.0175 / 100 PKR
    res1 = compute_execution_charges("SELL", 10000, 53.99, 539900.0, DEFAULT_SETTINGS)
    assert res1["commission_slab"] == "0.0175 paisa per share"
    assert pytest.approx(res1["commission_amount"], rel=1e-9) == 10000 * 0.0175 / 100.0  # 1.75 PKR
    assert pytest.approx(res1["sst_amount"], rel=1e-9) == res1["commission_amount"] * 0.13
    assert pytest.approx(res1["total_charges"], rel=1e-9) == res1["commission_amount"] + res1["sst_amount"]

    # Boundary: Sell price == 54.00 PKR -> Slab 2 (0.0325% of sell value)
    res2 = compute_execution_charges("SELL", 1000, 54.00, 54000.0, DEFAULT_SETTINGS)
    assert res2["commission_slab"] == "0.0325% of sell value"
    assert pytest.approx(res2["commission_amount"], rel=1e-9) == 54000.0 * 0.000325  # 17.55 PKR
    assert pytest.approx(res2["sst_amount"], rel=1e-9) == res2["commission_amount"] * 0.13
    assert pytest.approx(res2["total_charges"], rel=1e-9) == res2["commission_amount"] + res2["sst_amount"]

    # BUY side has zero commission/SST in this workbook rule set
    res_b = compute_execution_charges("BUY", 5000, 100.0, 500000.0, DEFAULT_SETTINGS)
    assert res_b["commission_amount"] == 0.0 and res_b["sst_amount"] == 0.0 and res_b["total_charges"] == 0.0


def test_tradelog_normalization_deduplication_and_unexpected_account_isolation():
    raw_log = (
        "Date,Time,Terminal,Market,Symbol,Transaction Type,Order ID,Execution ID,Account,Status,Quantity,Remaining Quantity,Order Quantity,Trade Price,Trade Value\n"
        "16/10/2026,10:00:01,THM00601,REG,OGDC,Buy,ORD001,EXEC001,91404,FILLED,1000,0,1000,200.00,200000.00\n"
        # Duplicate of EXEC001 in same file -> must be deduplicated
        "16/10/2026,10:00:01,THM00601,REG,OGDC,Buy,ORD001,EXEC001,91404,FILLED,1000,0,1000,200.00,200000.00\n"
        # Second partial fill on same Order ID ORD001 with distinct Execution ID EXEC002 -> must be kept!
        "16/10/2026,10:00:05,THM00601,REG,OGDC,Buy,ORD001,EXEC002,91404,FILLED,500,0,1500,202.00,101000.00\n"
        # Short Sell -> normalized to SELL while preserving raw_side = 'Short Sell'
        "16/10/2026,11:00:00,THM00601,FUT,TRG-OCT,Short Sell,ORD002,EXEC003,91404,FILLED,2000,0,2000,56.80,113600.00\n"
        # Unexpected account 99999 -> flagged and isolated
        "16/10/2026,11:05:00,THM00601,REG,LUCK,Buy,ORD003,EXEC004,99999,FILLED,100,0,100,900.00,90000.00\n"
    )
    res = parse_tradelog_content(raw_log, "sample_tradelog.csv")
    assert len(res["executions"]) == 3
    assert len(res["unexpected_account_rows"]) == 1
    assert res["unexpected_account_rows"][0]["account_id"] == "99999"

    short_exec = [e for e in res["executions"] if e["execution_id"] == "EXEC003"][0]
    assert short_exec["raw_side"] == "Short Sell"
    assert short_exec["normalized_side"] == "SELL"
    assert any(i["issue_type"] == "DUPLICATE_IN_FILE" for i in res["issues"])
    assert any(i["issue_type"] == "UNEXPECTED_ACCOUNT" for i in res["issues"])


def test_account_91404_and_91269_strict_separation_and_reconciliation():
    svc = AccountService()
    rep_91404 = svc.get_account_report("91404", selected_date="2026-10-16")
    rep_91269 = svc.get_account_report("91269", selected_date="2026-10-15")

    assert rep_91404["account_id"] == "91404"
    assert rep_91269["account_id"] == "91269"
    assert len(rep_91404["trading_dates"]) == 36
    assert len(rep_91269["trading_dates"]) == 20

    # Verify 16-Oct-2026 exact totals on Account 91404 from raw TradeLog-16-10-2026_ALL.txt
    d16 = rep_91404["selected_date_detail"]["summary"]
    assert pytest.approx(d16["buy_value"], abs=1e-4) == 4845060.0
    assert pytest.approx(d16["sell_value"], abs=1e-4) == 4855610.0
    assert pytest.approx(d16["gross_pnl"], abs=1e-4) == 10550.0
    assert pytest.approx(d16["commission_amount"], abs=1e-6) == 1578.07325
    assert pytest.approx(d16["sst_amount"], abs=1e-6) == 205.1495225
    assert pytest.approx(d16["net_pnl"], abs=1e-6) == 8766.7772275

    # Verify YTD reconciliation for both accounts
    assert rep_91404["data_checks"]["reconciliation"]["passed"] is True
    assert rep_91269["data_checks"]["reconciliation"]["passed"] is True
    assert pytest.approx(rep_91404["ytd_summary"]["net_pnl"], abs=1e-4) == 193263.6109
    assert pytest.approx(rep_91269["ytd_summary"]["net_pnl"], abs=1e-4) == 35658.9535


def test_daily_summary_symbols_column_and_symbol_performance_dates_column():
    """
    Dashboard workbook-alignment guards:
    - Every Daily Summary row exposes the exact traded symbols for that date.
    - Every Symbol Performance row exposes the exact trading dates for that symbol.
    - Symbol Performance also provides an overall TOTAL row + Best/Worst flags.
    """
    svc = AccountService()
    rep_91269 = svc.get_account_report("91269")

    # Daily Summary (21 rows incl. TOTAL in UI) must carry symbols per date
    daily_rows = rep_91269["daily_summary"]["rows"]
    assert len(daily_rows) == 20
    first_row = daily_rows[0]
    assert first_row["trade_date"] == "2026-08-24"
    assert first_row["symbols_count"] >= 1
    assert "OGDC" in first_row["symbols_str"]
    assert rep_91269["daily_summary"]["total"]["symbols_count"] == 31

    # MTD/QTD/YTD must expose the full date-by-date breakdown (matching workbook sheets)
    for block_key in ["mtd_summary", "qtd_summary", "ytd_summary"]:
        blk = rep_91269[block_key]
        assert blk["trading_days"] == len(blk["daily_rows"])
        assert all(r["symbols_count"] >= 1 for r in blk["daily_rows"])
    assert rep_91269["ytd_summary"]["trading_days"] == 20

    # Symbol Performance must carry dates for every symbol + TOTAL row + notes
    sp = rep_91269["symbol_performance"]
    assert len(sp) == 31
    for r in sp:
        assert r["trading_days"] == len(r["dates_list"])
        assert r["first_date"] <= r["last_date"]
        assert r["dates_display"]
    assert sp[0]["note"] == "◄ Best performer"
    assert sp[-1]["note"] == "◄ Worst performer"
    tot = rep_91269["symbol_performance_total"]
    assert tot is not None and tot["symbol"] == "TOTAL"
    assert pytest.approx(tot["net_pnl"], abs=1e-4) == 35658.9535
    assert sum(tot["trading_days"] for _ in [1]) == 20
