from pathlib import Path
import os
import pytest
from fastapi.testclient import TestClient
from psx_app.config import CORE_36_TICKERS
from psx_app.main import app
from psx_app.services.backup_service import BackupService
from psx_app.services.reconciliation_service import ReconciliationService
from psx_app.services.technical_service import TechnicalService


def test_core_36_tickers_and_mlf_mlcf_alias():
    svc = TechnicalService()
    uni = svc.get_universe_summary(scope="core36")
    assert uni["count"] == 36
    assert set(CORE_36_TICKERS) == {item["symbol"] for item in uni["items"]}

    # Verify MLF alias resolves cleanly to MLCF
    mlf_res = svc.get_ticker_analysis("MLF")
    mlcf_res = svc.get_ticker_analysis("MLCF")
    assert mlf_res["symbol"] == "MLCF"
    assert mlf_res["latest"]["close"] == mlcf_res["latest"]["close"]


def test_atrl_indicators_pivots_and_no_future_leakage():
    svc = TechnicalService()
    atrl = svc.get_ticker_analysis("ATRL", tail_bars=196)
    lat = atrl["latest"]

    assert pytest.approx(lat["close"], abs=1e-2) == 1219.10
    assert pytest.approx(lat["rsi14"], abs=1e-2) == 63.21
    assert pytest.approx(lat["macd"], abs=1e-2) == 26.54
    assert pytest.approx(lat["macd_sig"], abs=1e-2) == 27.55
    assert pytest.approx(lat["macd_hist"], abs=1e-2) == -1.01
    assert pytest.approx(lat["bb_up"], abs=1e-2) == 1237.32
    assert pytest.approx(lat["bb_mid"], abs=1e-2) == 1181.35
    assert pytest.approx(lat["bb_low"], abs=1e-2) == 1125.37
    assert pytest.approx(lat["ema9"], abs=1e-2) == 1199.85
    assert pytest.approx(lat["ema21"], abs=1e-2) == 1177.77
    assert pytest.approx(lat["ema50"], abs=1e-2) == 1121.94
    assert lat["ema200"] is None  # Strict < 200 bars rule (196 bars)
    assert pytest.approx(lat["ema200_recursive"], abs=1e-2) == 951.04
    assert pytest.approx(lat["adx14"], abs=1e-2) == 41.03

    # Verify Daily Classic Pivot on 2026-10-16 (High=1226, Low=1207, Close=1219.1)
    dp = lat["daily_pivots"]["classic"]
    assert pytest.approx(dp["P"], abs=1e-2) == 1217.37
    assert pytest.approx(dp["R1"], abs=1e-2) == 1227.73
    assert pytest.approx(dp["S1"], abs=1e-2) == 1208.73

    # Verify no future-data leakage: computing indicators on first 150 bars must match bar[149] of full 196-bar series
    full_series = atrl["series"]
    raw_150 = [
        {
            "trade_date": b["trade_date"],
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "pr_close": b["pr_close"],
            "volume": b["volume"],
        }
        for b in full_series[:150]
    ]
    trunc_res = svc.calculate_series_for_bars("ATRL", raw_150)
    trunc_series = trunc_res["series"]
    assert pytest.approx(trunc_series[-1]["rsi14"], abs=1e-9) == full_series[149]["rsi14"]
    assert pytest.approx(trunc_series[-1]["macd"], abs=1e-9) == full_series[149]["macd"]


def test_insufficient_history_handling():
    svc = TechnicalService()
    short_bars = [
        {
            "trade_date": f"2026-01-{i:02d}",
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 99.0 + i,
            "close": 101.0 + i,
            "pr_close": 100.0 + i,
            "volume": 1000,
        }
        for i in range(1, 10)
    ]
    out = svc.calculate_series_for_bars("SHORT", short_bars)
    assert out["latest"]["rsi14"] is None
    assert out["latest"]["macd"] is None
    assert out["latest"]["signal"]["action"] == "INSUFFICIENT DATA"


def test_reconciliation_backup_and_fastapi_endpoints():
    recon = ReconciliationService().reconcile_against_legacy_workbooks()
    assert recon["module_a_top5"]["status"] == "MATCH"
    assert recon["module_b_account_91404"]["status"] == "MATCH"
    assert recon["module_b_account_91269"]["status"] == "MATCH"
    assert recon["module_c_futures"]["status"] == "MATCH"
    assert recon["module_d_technical_atrl"]["status"] == "MATCH"

    b_svc = BackupService()
    chk = b_svc.run_integrity_check()
    assert chk["ok"] is True

    client = TestClient(app)
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_ov = client.get("/api/overview")
    assert r_ov.status_code == 200
    assert r_ov.json()["system"]["top5"]["records"] == 4805

    # Verify new Trading Ideas Generator & Automated Technical Analyst endpoints
    r_ideas = client.get("/api/intelligence/trading-ideas?scope_or_sector=CORE36&direction=ALL")
    assert r_ideas.status_code == 200
    assert len(r_ideas.json()["setups"]) == 5

    r_analyst = client.get("/api/intelligence/automated-analyst/ATRL")
    assert r_analyst.status_code == 200
    assert len(r_analyst.json()["step_by_step_analysis"]) == 5

    # Verify Futures & Settings endpoints
    r_fut = client.get("/api/futures/comparison?view_mode=monthly_comparison")
    assert r_fut.status_code == 200
    assert "dates" in client.get("/api/futures/metadata").json()

    r_set = client.get("/api/settings")
    assert r_set.status_code == 200
    assert "rule_versions" in r_set.json()


def test_incremental_upload_staging_and_idempotency():
    import shutil
    from psx_app.config import RAW_DIR
    from psx_app.database.schema import get_connection

    client = TestClient(app)
    atrl_bytes = open(str(Path(os.environ["PSX_TEST_REFERENCE_DIR"]) / "Input folder" / "ATRL.txt"), "rb").read()
    res_stage = client.post(
        "/api/imports/stage",
        files=[("files", ("ATRL.txt", atrl_bytes, "text/plain"))],
    )
    assert res_stage.status_code == 200
    staged = res_stage.json()
    assert staged["files_count"] == 1
    assert staged["duplicates_ignored"] == 5
    assert staged["new_records"] == 0

    res_commit = client.post(
        "/api/imports/commit",
        json={"batch_uuid": staged["batch_uuid"], "allow_revisions": True},
    )
    assert res_commit.status_code == 200
    committed = res_commit.json()
    assert committed["status"] == "COMMITTED"
    assert committed["new_records"] == 0
    assert committed["duplicates_ignored"] == 5

    # Clean up test batch artifact so production DB and raw archive stay clean
    b_uuid = staged["batch_uuid"]
    conn = get_connection()
    row = conn.execute("SELECT id FROM import_batches WHERE batch_uuid=?", (b_uuid,)).fetchone()
    if row:
        conn.execute("DELETE FROM import_issues WHERE batch_id=?", (row["id"],))
        conn.execute("DELETE FROM source_revisions WHERE batch_id=?", (row["id"],))
        conn.execute("DELETE FROM source_files WHERE archive_path LIKE ?", (f"%{b_uuid}%",))
        conn.execute("DELETE FROM import_batches WHERE id=?", (row["id"],))
        conn.commit()
    conn.close()
    shutil.rmtree(RAW_DIR / b_uuid, ignore_errors=True)

