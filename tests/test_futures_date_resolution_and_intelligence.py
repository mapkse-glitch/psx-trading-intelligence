from fastapi.testclient import TestClient
from psx_app.main import app


def test_futures_comparison_resolves_non_trading_calendar_date():
    client = TestClient(app)
    # metadata tells us real available dates
    meta = client.get("/api/futures/metadata?apply_rolling=true").json()
    avail = sorted(meta["dates"])
    assert avail, "expected futures data available"
    latest = avail[-1]

    # Request a clearly non-trading Sunday date near the latest data day
    picked = "2026-10-18"
    assert picked not in avail
    res = client.get(
        f"/api/futures/comparison?view_mode=monthly_comparison&selected_date={picked}&days=30&apply_rolling=true"
    ).json()
    assert res["date_was_resolved"] is True
    assert res["requested_date"] == picked
    assert res["selected_date"] == latest  # Sunday 18-Oct-2026 -> nearest earlier Friday 16-Oct
    assert res["rows_count"] > 0

    # Exact trading-day request is NOT resolved, parity row count preserved
    res_exact = client.get(
        f"/api/futures/comparison?view_mode=monthly_comparison&selected_date={latest}&days=30&apply_rolling=true"
    ).json()
    assert res_exact["date_was_resolved"] is False
    assert res_exact["selected_date"] == latest
    assert res_exact["rows_count"] == res["rows_count"]


def test_date_summary_resolves_calendar_date_and_returns_ooc_note():
    client = TestClient(app)
    res = client.get("/api/futures/date-summary?selected_date=2026-10-18&apply_rolling=true").json()
    assert res["date_was_resolved"] is True
    assert res["requested_date"] == "2026-10-18"
    assert res["rows_count"] > 0


def test_all_dates_modes_still_untouched_by_resolution():
    client = TestClient(app)
    for sd in ("ALL", "ALL_HISTORY"):
        res = client.get(
            f"/api/futures/comparison?view_mode=symbol_filter&selected_date={sd}&contract_month=OCTB&base_symbol=OGDC&days=30&apply_rolling=true"
        ).json()
        assert sd == res["selected_date"]
        assert res["date_was_resolved"] is False


def test_intelligence_cards_are_data_only_and_enriched():
    client = TestClient(app)
    ideas = client.get("/api/intelligence/trading-ideas?scope_or_sector=CORE36&direction=ALL").json()
    assert "prompt_used" not in ideas
    assert len(ideas["setups"]) == 5
    for st in ideas["setups"]:
        for k in ("rsi14", "adx14", "volume_ratio", "trend_state", "momentum_state", "invalidation", "weekly_pivot_p"):
            assert k in st, f"setup missing analytic field {k}"

    analyst = client.get("/api/intelligence/automated-analyst/ATRL").json()
    assert "prompt_used" not in analyst
    assert len(analyst["step_by_step_analysis"]) == 5
    ss = analyst["structure_snapshot"]
    for k in ("weekly_trend", "price_vs_daily_pivot", "ma_alignment", "rsi_zone", "adx_strength", "macd_momentum"):
        assert ss.get(k)
    kl = analyst["key_levels"]
    for k in ("daily_pivot", "r1", "r2", "s1", "s2", "weekly_pivot", "swing_high_20d", "swing_low_20d", "regression_center", "upper_channel", "lower_channel"):
        assert kl.get(k) is not None, f"key_levels missing {k}"
