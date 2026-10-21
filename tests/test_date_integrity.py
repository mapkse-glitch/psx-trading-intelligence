"""Regression tests for the day/month-swap date defect.

Covers:
1. Pinned date parsing semantics in parsers/ohlcv_parser.py (no more silent
   MM-DD/DD-MM swaps, plus file-level orientation detection);
2. The anchor-driven DateRepairService: plan (dry-run), apply, collision and
   idempotency guarantees on a synthetic sqlite database.
"""

import csv
import sqlite3
from pathlib import Path

from psx_app.database.schema import DDL_STATEMENTS, get_connection, init_db
from psx_app.parsers.ohlcv_parser import (
    detect_date_orientation,
    parse_any_date,
    parse_ohlcv_file,
)
from psx_app.services.date_repair_service import DateRepairService
from datetime import datetime


class TestPinnedDateParsing:
    def test_datetime_and_iso_pass_through(self):
        assert parse_any_date(datetime(2026, 9, 2)) == "2026-09-02"
        assert parse_any_date("2026-09-02") == "2026-09-02"
        assert parse_any_date("2026-09-02 00:00:00") == "2026-09-02"

    def test_slash_is_us_mdy(self):
        # Google Sheets US-locale CSV export: 10/12/2026 = October 12 (NOT Dec 10)
        assert parse_any_date("10/12/2026") == "2026-10-12"
        assert parse_any_date("9/1/2026") == "2026-09-01"
        assert parse_any_date("10/20/2026") == "2026-10-20"

    def test_dash_is_workbook_dmy(self):
        # Google Sheets DMY dash convention: 12-10-2026 = October 12
        assert parse_any_date("12-10-2026") == "2026-10-12"
        assert parse_any_date("09-11-2026") == "2026-11-09"

    def test_impossible_month_falls_through(self):
        # 20/10/2026 cannot be MDY -> walk to the DMY interpretation
        assert parse_any_date("20/10/2026") == "2026-10-20"
        # 10-20-2026 cannot be DMY -> walk to MDY
        assert parse_any_date("10-20-2026") == "2026-10-20"

    def test_named_month_and_invalid(self):
        assert parse_any_date("12-Oct-2026") == "2026-10-12"
        assert parse_any_date("") is None
        assert parse_any_date(None) is None
        assert parse_any_date("n/a") is None

    def test_prefer_overrides_separator_policy(self):
        assert parse_any_date("09/10/2026", prefer="DMY") == "2026-10-09"
        assert parse_any_date("09-10-2026", prefer="MDY") == "2026-09-10"


class TestOrientationDetection:
    def test_dmy_forced_by_day_gt_12(self):
        vals = ["01-09-2026", "02-09-2026", "13-09-2026", "20-10-2026"]
        o = detect_date_orientation(vals)
        assert o["prefer"] == "DMY" and o["decision"] == "dmy-forced-by-data"

    def test_mdy_forced_by_day_gt_12(self):
        vals = ["9/1/2026", "9/15/2026", "10/20/2026"]
        o = detect_date_orientation(vals)
        assert o["prefer"] == "MDY" and o["decision"] == "mdy-forced-by-data"

    def test_ambiguous_defaults(self):
        o = detect_date_orientation(["01/02/2026", "03/04/2026"])
        assert o["prefer"] is None and o["decision"] == "separator-policy-default"
        o2 = detect_date_orientation(["01-02-2026", "03-04-2026"])
        assert o2["prefer"] is None

    def test_real_datetimes_ignored(self):
        o = detect_date_orientation([datetime(2026, 8, 4), datetime(2026, 10, 20)])
        assert o["numeric"] == 0 and o["non_numeric"] == 2


class TestOhlcvCsvNoSwap:
    def test_us_csv_dates_never_swap(self, tmp_path):
        p = tmp_path / "2026F.csv"
        rows = [
            ["Date", "Symbol", "PR_CL", "OPEN", "High", "LOW", "AVG", "CLOSE", "VOLUME"],
            ["8/4/2026", "OGDC-OCT", "300.0", "301.0", "305.0", "299.0", "302.0", "303.0", "1000"],
            ["9/1/2026", "OGDC-OCT", "303.0", "304.0", "306.0", "302.0", "304.0", "305.0", "1500"],
            ["10/12/2026", "OGDC-OCTB", "308.25", "310.0", "308.57", "300.07", "304.0", "302.17", "664000"],
            ["10/20/2026", "OGDC-OCTB", "302.17", "300.0", "303.0", "299.61", "301.0", "301.35", "355500"],
        ]
        with open(p, "w", newline="") as fh:
            csv.writer(fh).writerows(rows)

        res = parse_ohlcv_file(p, mode="FUTURES", original_filename="2026F.csv")
        dates = sorted({r["trade_date"] for r in res["records"]})
        # the historical defect would have produced 2026-01-08/2026-01-09/2026-12-10 etc.
        assert dates == ["2026-08-04", "2026-09-01", "2026-10-12", "2026-10-20"]
        assert all(r["trade_date"][5:7] in ("08", "09", "10") for r in res["records"])
        pin_notes = [i for i in res["issues"] if i["issue_type"] == "DATE_FORMAT_PINNED"]
        assert pin_notes and "mdy" in pin_notes[0]["message"].lower()


# --------------------------------------------------------------------------
# Repair service on a synthetic database
# --------------------------------------------------------------------------

def _make_db(root: Path) -> Path:
    """Empty-schema DB. NOTE: init_db() auto-hydrates from the bundled
    latest_cloud_sync.db.gz snapshot when the target is empty, so tests must
    apply the raw DDL instead to stay hermetic."""
    db_dir = root / "rt" / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    db = db_dir / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript(DDL_STATEMENTS)
    conn.commit()
    conn.close()
    return db


def _seed_futures(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    rows = [
        # true anchor rows (day > 12 -> provably real)
        ("2026-08-13", "OGDC-OCT", 10, 290.0, 295.0, 288.0, 289.0, 294.0, 292.0, 4.0, "2026F.xlsx"),
        ("2026-10-20", "OGDC-OCTB", 20, 302.17, 303.0, 303.0, 299.61, 301.35, 301.0, -0.82, "2026F.xlsx"),
        # phantom: 2026-12-10 == 12-10-2026 with the TRUE row present at 2026-10-12
        ("2026-10-12", "OGDC-OCTB", 30, 308.25, 310.0, 308.57, 300.07, 302.17, 304.0, -6.08, "2026F.xlsx"),
        ("2026-12-10", "OGDC-OCTB", 30, 308.25, 310.0, 308.57, 300.07, 302.17, 304.0, -6.08, "2026F.csv"),
        # past-side phantom: text 9/1/2026 read as Jan 9 (true row exists at 2026-09-01)
        ("2026-09-01", "OGDC-OCT", 40, 303.0, 306.0, 302.0, 304.0, 305.0, 304.0, 2.0, "2026F.xlsx"),
        ("2026-01-09", "OGDC-OCT", 40, 303.0, 306.0, 302.0, 304.0, 305.0, 304.0, 2.0, "2026F.csv"),
        # genuine early-season row (day <= 12 but LEGIT - Aug 4): must survive
        ("2026-08-04", "OGDC-OCT", 50, 300.0, 305.0, 299.0, 302.0, 303.0, 302.0, 3.0, "2026F.xlsx"),
        # in-window residual pollution from .csv with equal dup at true date
        ("2026-10-09", "OGDC-OCT", 60, 290.0, 292.0, 293.0, 289.0, 291.0, 291.0, 1.0, "2026F.xlsx"),
        ("2026-09-10", "OGDC-OCT", 60, 290.0, 292.0, 293.0, 289.0, 291.0, 291.0, 1.0, "2026F.csv"),
        # a real unique mid-season row with day<=12 -> survives (no equal dup for its flip)
        ("2026-08-11", "OGDC-OCT", 70, 280.0, 283.0, 279.0, 281.0, 282.0, 281.0, 2.0, "2026F.csv"),
    ]
    rows = [(td, cs, cs.split("-")[0], cs.split("-")[1], vol, pc, op, hi, lo, cl, av, cv, src) for (td, cs, vol, pc, op, hi, lo, cl, av, cv, src) in rows]
    conn.executemany(
        """INSERT INTO futures_ohlcv
           (trade_date, contract_symbol, base_symbol, contract_month, volume, pr_close, open, high, low, close, avg_price, change_val, source_filename)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()


class TestDateRepairService:
    def test_plan_apply_idempotent(self, tmp_path):
        db = _make_db(tmp_path)
        _seed_futures(db)
        svc = DateRepairService(db_path=db, data_root=tmp_path / "rt")

        plan = svc.plan()
        fut = [t for t in plan["tables"] if t["table"] == "futures_ohlcv"][0]
        # 3 provable phantom rows: future-dup, past-dup, in-window csv dup; 0 conflicts
        assert fut["candidates"] == 3
        assert fut["duplicate_drop"] == 3
        assert fut["conflict"] == 0

        res = svc.apply()
        assert res["status"] == "APPLIED"
        assert res["idempotent_check"] == "PASS"
        assert Path(res["backup_path"]).exists()

        conn = sqlite3.connect(db)
        remaining = [r[0] for r in conn.execute("SELECT DISTINCT trade_date FROM futures_ohlcv ORDER BY 1")]
        conn.close()
        # phantoms gone, legit rows untouched
        assert "2026-12-10" not in remaining
        assert "2026-01-09" not in remaining
        assert "2026-09-10" not in remaining
        assert remaining == ["2026-08-04", "2026-08-11", "2026-08-13", "2026-09-01", "2026-10-09", "2026-10-12", "2026-10-20"]

        # second run repairs nothing
        again = svc.plan()
        assert again["totals"]["candidates"] == 0

    def test_conflict_prefers_xlsx_source(self, tmp_path):
        db = _make_db(tmp_path)
        conn = sqlite3.connect(db)
        # NOTE: phantoms always store with DAY <= 12 (a swap can never raise
        # the day above 12), so use day-10/11 rows to exercise the conflict path.
        seed = [
            ("2026-08-13", "OGDC-OCT", 10, 290.0, 295.0, 288.0, 289.0, 294.0, 292.0, 4.0, "2026F.xlsx"),
            ("2026-10-20", "OGDC-OCT", 12, 291.0, 296.0, 289.0, 290.0, 295.0, 293.0, 5.0, "2026F.xlsx"),
            # canonical row at the phantom's true date, xlsx-sourced
            ("2026-10-11", "OGDC-OCT", 11, 291.0, 296.0, 289.0, 290.0, 295.0, 293.0, 5.0, "2026F.xlsx"),
            # future-side phantom (10-11-2026 -> 11-10-2026) with DIFFERING values from csv
            ("2026-11-10", "OGDC-OCT", 99, 999.0, 999.0, 999.0, 999.0, 999.0, 999.0, 9.0, "2026F.csv"),
        ]
        seed = [(td, cs, cs.split("-")[0], cs.split("-")[1], vol, pc, op, hi, lo, cl, av, cv, src) for (td, cs, vol, pc, op, hi, lo, cl, av, cv, src) in seed]
        conn.executemany(
            """INSERT INTO futures_ohlcv
               (trade_date, contract_symbol, base_symbol, contract_month, volume, pr_close, open, high, low, close, avg_price, change_val, source_filename)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            seed,
        )
        conn.commit()
        conn.close()
        svc = DateRepairService(db_path=db, data_root=tmp_path / "rt")
        plan = svc.plan()
        fut = [t for t in plan["tables"] if t["table"] == "futures_ohlcv"][0]
        assert fut["conflict"] == 1
        svc.apply()
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT close, source_filename FROM futures_ohlcv WHERE trade_date='2026-11-10'"
        ).fetchone()
        assert row is None
        keep = conn.execute(
            "SELECT close, source_filename FROM futures_ohlcv WHERE trade_date='2026-10-11'"
        ).fetchone()
        # xlsx-sourced canonical row wins the conflict
        assert keep and abs(keep[0] - 295.0) < 1e-6 and keep[1].endswith(".xlsx")
        quarantine = conn.execute(
            "SELECT COUNT(*) FROM import_issues WHERE issue_type='DATE_NORMALIZATION_COLLISION'"
        ).fetchone()[0]
        assert quarantine == 1
        conn.close()
