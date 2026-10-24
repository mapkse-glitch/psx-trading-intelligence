from psx_app.services.result_cache import persisted_result
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import CORE_36_TICKERS
from psx_app.database.schema import get_connection
from psx_app.services.technical_service import TechnicalService

from psx_app.services.sector_reference import SectorReference

# Sector classification is file-backed; no hard-coded fundamental claims.
PSX_SECTOR_MAP = {}  # Legacy import compatibility only; runtime uses SectorReference.


class IntelligenceService:
    """
    Powers the two interactive institutional intelligence cards:
      1. Trading Ideas Generator (Top 5 High-Probability Setups with Entry, Targets, Stop-Loss, R/R, Technical & Fundamental Why)
      2. Automated Technical Analyst (Daily & Weekly Chart Analysis, S/R, Trend Lines, Moving Averages, Momentum & Step-by-Step Signal)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.tech_service = TechnicalService(db_path)
        self.reference = SectorReference(db_path)
        self.sector_map = {sym:dict(row, fundamental='Fundamentals unavailable; no verified financial/news input supplied.') for sym,row in self.reference.directory().items()}

    def get_available_sectors_and_filters(self) -> Dict[str, Any]:
        sectors = sorted({v["sector"] for v in self.sector_map.values()})
        return {
            "presets": [
                {"id": "CORE36", "label": "Core 36 Institutional Watchlist"},
                {"id": "TOP5_VOL", "label": "Top 5 Volume Register Symbols"},
                {"id": "FUTURES", "label": "Same-session Futures-observed Symbols (eligibility unverified)"},
                {"id": "ALL_MARKET", "label": "All Imported Cash Symbols (includes historical/inactive symbols)"},
            ],
            "sectors": sectors,
            "reference_lists": list(self.reference.lists()),
            "core_tickers": CORE_36_TICKERS,
        }

    @persisted_result
    def generate_trading_ideas(
        self,
        scope_or_sector: str = "CORE36",
        direction_filter: str = "ALL",
        custom_query: str = "",
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Scan today's market and generate 5 rule-scored trading candidates for the selected
        stock/index/sector. Includes Entry, Target 1, Target 2, Stop-Loss, Risk/Reward ratio,
        and explains why each setup works based on technical and fundamental/liquidity factors.
        """
        from psx_app.services.data_guard import date_integrity
        integrity = date_integrity(self.db_path)
        if not integrity["ok"]:
            return {"status": "BLOCKED", "message": integrity["message"], "date_integrity": integrity,
                    "target_label": custom_query or scope_or_sector, "candidates_scanned": 0, "setups_count": 0, "setups": []}
        # Compute available indicators before filtering; a rejected symbol was still examined.
        direction_filter = direction_filter.strip().upper()
        if direction_filter not in ("ALL", "LONG", "SHORT"):
            raise ValueError("Direction must be ALL, LONG or SHORT.")
        limit = max(1, min(5, int(limit)))
        with get_connection(self.db_path) as c:
            cash_symbols = {r[0] for r in c.execute("SELECT DISTINCT symbol FROM equity_ohlcv")}
            market_date = c.execute("SELECT MAX(trade_date) FROM equity_ohlcv").fetchone()[0]
            top5_tickers = {(r["ticker"], r["trade_date"]): r["top_vol"] for r in c.execute(
                "SELECT ticker, trade_date, SUM(volume) AS top_vol FROM top5_volume_records GROUP BY ticker, trade_date")}
            fut_map = {}
            for row in c.execute("SELECT base_symbol, trade_date, close, contract_symbol, volume FROM futures_ohlcv ORDER BY volume DESC, contract_symbol ASC"):
                fut_map.setdefault((row["base_symbol"], row["trade_date"]), dict(row))

        q_clean = self.tech_service.resolve_ticker(custom_query.strip()) if custom_query.strip() else ""
        exact_query = q_clean in cash_symbols
        filtered, rejected, diagnostics, outside_scope = [], [], [], []
        counts = dict(universe_total=len(cash_symbols), query_matches=0, matched=0, analyzed=0,
                      data_ready=0, direction_eligible=0, structurally_qualified=0, displayed=0)
        ref_lists = self.reference.lists()
        membership = {r['symbol'] for r in ref_lists.get(scope_or_sector, [])}
        core = set(CORE_36_TICKERS)
        if q_clean:
            selected = {sym for sym in cash_symbols if (sym == q_clean if exact_query else q_clean in sym or q_clean in self.sector_map.get(sym, {}).get("sector", "").upper())}
        elif scope_or_sector in ref_lists: selected = cash_symbols & membership
        elif scope_or_sector == "CORE36": selected = cash_symbols & core
        elif scope_or_sector == "TOP5_VOL": selected = cash_symbols & {sym for sym, _ in top5_tickers}
        elif scope_or_sector == "FUTURES": selected = cash_symbols & {sym for sym, dt in fut_map if dt == market_date}
        elif scope_or_sector == "ALL_MARKET": selected = cash_symbols
        else: selected = {sym for sym in cash_symbols if self.sector_map.get(sym, {}).get("sector", "").casefold() == scope_or_sector.casefold()}
        # Never calculate unrelated symbols when scanning a single ticker/watchlist.
        items = self.tech_service.get_universe_summary(scope="all", symbols=sorted(selected))["items"]
        for it in items:
            sym = it["symbol"]
            sector = self.sector_map.get(sym, {}).get("sector", "Unclassified")
            if q_clean and not (sym == q_clean if exact_query else q_clean in sym or q_clean in sector.upper()):
                continue
            counts["query_matches"] += 1
            in_scope = (
                sym in membership if scope_or_sector in ref_lists else
                sym in core if scope_or_sector == "CORE36" else
                (sym, it["latest_date"]) in top5_tickers if scope_or_sector == "TOP5_VOL" else
                bool(it.get("is_futures_eligible")) if scope_or_sector == "FUTURES" else
                True if scope_or_sector == "ALL_MARKET" else sector.casefold() == scope_or_sector.casefold())
            if not in_scope:
                if q_clean:
                    outside_scope.append(dict(symbol=sym, code="OUTSIDE_SCOPE", reason="Cash history exists, but symbol is outside the selected scope. Select All imported cash symbols to inspect it.", bars_count=it["bars_count"]))
                continue
            counts["matched"] += 1
            counts["analyzed"] += 1
            sig = it.get("signal") or {}
            score = int(sig.get("score") or 0)
            plan = sig.get("trade_plan") or {}
            reasons = []
            if it.get("data_freshness", {}).get("status") == "STALE":
                reasons.append(dict(code="STALE_DATA", reason=f"Last cash session {it['latest_date']} is behind the latest imported cash session. Historical data exists; no current-session entry."))
            if float(it.get("volume") or 0) <= 0:
                reasons.append(dict(code="ZERO_VOLUME", reason="No positive reported volume in the symbol's last cash session."))
            if it["bars_count"] < 26 or it.get("rsi14") is None or sig.get("combined_signal") == "INSUFFICIENT DATA":
                reasons.append(dict(code="INSUFFICIENT_HISTORY", reason=f"{it['bars_count']} stored cash sessions; available indicators do not meet signal readiness. No synthetic history is substituted."))
            ready = not reasons
            counts["data_ready"] += int(ready)
            direction_ok = not ((direction_filter == "LONG" and score < 1) or (direction_filter == "SHORT" and score > -1))
            if not direction_ok:
                reasons.append(dict(code="DIRECTION_FILTER", reason=f"Raw signal {sig.get('combined_signal', 'unavailable')} ({score:+d}/9) is excluded by {direction_filter}. This is a filter rejection, not missing data."))
            counts["direction_eligible"] += int(ready and direction_ok)
            if plan.get("status") != "VALID":
                reasons.append(dict(code="NO_VALID_PLAN", reason=plan.get("reason") or "No validated structural entry/stop/target plan."))
            elif direction_filter in ("LONG", "SHORT") and plan.get("side") != direction_filter:
                reasons.append(dict(code="PLAN_DIRECTION", reason="Structural plan is opposite to the selected direction."))
            row = dict(symbol=sym, sector=sector, score=score, raw_signal=sig.get("combined_signal"),
                       first_date=it["first_date"], latest_date=it["latest_date"], bars_count=it["bars_count"],
                       reasons=reasons, status="REJECTED" if reasons else "QUALIFIED",
                       reason="; ".join(r["reason"] for r in reasons) if reasons else "Passed data, direction and structural safeguards.")
            diagnostics.append(row)
            if reasons: rejected.append(row)
            else: filtered.append(it)
        counts["structurally_qualified"] = len(filtered)

        # Rank setups by composite conviction: |score|*10 + ADX strength + volume ratio + R/R quality
        scored_setups: List[Dict[str, Any]] = []
        for it in filtered:
            sym = it["symbol"]
            c_price = float(it["close"])
            sig = it["signal"]
            score = int(sig["score"])
            adx = float(it.get("adx14") or 15.0)
            rsi = float(it.get("rsi14") or 50.0)
            vol = float(it.get("volume") or 0)
            vol_avg = float(it.get("volume_20d_avg") or 1.0)
            vol_ratio = vol / max(vol_avg, 1.0)

            dp = it["daily_pivots"]["classic"]
            wp = (it.get("weekly_pivots") or {}).get("pivots") or {}
            p, r1, r2, r3, s1, s2 = dp["P"], dp["R1"], dp["R2"], dp["R3"], dp["S1"], dp["S2"]
            e21 = float(it.get("ema21") or c_price)
            e50 = float(it.get("ema50") or c_price)

            # One validated execution plan is shared with the deep-dive and analyst.
            plan = sig.get("trade_plan") or {}
            if plan.get("status") != "VALID":
                rejected.append({'symbol':sym,'reason':plan.get('reason','No valid structural entry.'),'score':score})
                continue
            is_bullish = plan["side"] == "LONG"
            if direction_filter == "LONG" and not is_bullish:
                continue
            if direction_filter == "SHORT" and is_bullish:
                continue
            setup_type = "LONG / STRUCTURAL SETUP" if is_bullish else "FUTURES SHORT CANDIDATE / VERIFY ELIGIBILITY"
            entry_price, stop_loss = plan["entry"], plan["stop"]
            target_1, target_2 = plan["target_1"], plan["target_2"]
            risk = abs(entry_price - stop_loss)
            rr_t1 = abs(target_1 - entry_price) / risk
            rr_t2 = abs(target_2 - entry_price) / risk

            # Conviction ranking metric (deterministic)
            dir_alignment = score if is_bullish else -score
            conviction_raw = (
                dir_alignment * 8.5
                + min(adx, 45.0) * 0.45
                + min(vol_ratio, 3.0) * 6.0
                + (5.0 if (sym, it["latest_date"]) in top5_tickers else 0.0)
                + min(rr_t2, 4.0) * 3.0
            )
            prob_pct = min(100, max(0, int(round(conviction_raw))))
            grade = "STRONG RULE AGREEMENT" if prob_pct >= 75 else ("MODERATE RULE AGREEMENT" if prob_pct >= 50 else "WEAK RULE AGREEMENT")

            sec_info = self.sector_map.get(sym, {
                "sector": "PSX Listed Equity",
                "fundamental": "Fundamentals unavailable; no verified financial/news input supplied.",
            })

            macd_v = it.get("macd") or 0.0
            macd_s = it.get("macd_sig") or 0.0
            macd_h = it.get("macd_hist") or 0.0

            ema9_v = float(it.get("ema9") or 0.0)
            trend_state = (
                "Bullish stack (EMA 9 > 21 > 50)"
                if ema9_v >= e21 >= e50
                else ("Bearish stack (EMA 9 < 21 < 50)" if ema9_v <= e21 <= e50 else "Mixed / transitioning MAs")
            )
            momentum_state = (
                f"{'Rising' if macd_h > 0 else 'Fading'} (MACD Hist {macd_h:+.3f})"
            )
            if is_bullish:
                invalidation = f"Below {stop_loss:.2f} PKR — daily pivot support S1={s1:.2f} / EMA-21={e21:.2f} zone."
            else:
                invalidation = f"Above {stop_loss:.2f} PKR — daily pivot resistance R1={r1:.2f} / EMA-21={e21:.2f} zone."

            tech_reasons = [
                f"Composite Score {score:+d}/9 ({sig['combined_signal']}) with Wilder RSI(14) at {rsi:.2f} ({it['rsi_zone']}).",
                f"Price ({c_price:.2f} PKR) vs EMA stack: EMA9={it.get('ema9') or 0:.2f}, EMA21={e21:.2f}, EMA50={e50:.2f}.",
                f"Daily Classic Pivot P={p:.2f} (R1={r1:.2f}, R2={r2:.2f}, S1={s1:.2f}) & Weekly Pivot W-P={wp.get('P') or p:.2f}.",
                f"ADX(14)={adx:.1f} (+DI={it.get('plus_di') or 0:.1f} / -DI={it.get('minus_di') or 0:.1f}) and MACD({macd_v:.2f} vs Sig {macd_s:.2f}, Hist {macd_h:+.2f}).",
            ]

            liq_notes = ["Fundamentals unavailable: no verified current financial statements/news supplied."]
            if (sym, it["latest_date"]) in top5_tickers:
                liq_notes.append(
                    f"Same-date Top 5 register context (not proof of institutional ownership): {top5_tickers[(sym, it['latest_date'])]:,} shares across ranked blocks on {it['latest_date']}."
                )
            if (sym, it["latest_date"]) in fut_map and c_price > 0:
                selected_future = fut_map[(sym, it["latest_date"])]
                f_px = selected_future["close"]
                spread_pct = (f_px - c_price) / c_price * 100.0
                liq_notes.append(
                    f"Same-date futures context: {selected_future['contract_symbol']} close {f_px:.2f} PKR ({spread_pct:+.2f}% basis vs cash), selected by highest reported volume on {it['latest_date']}."
                )
            liq_notes.append(
                f"Session volume {int(vol):,} shares ({vol_ratio:.2f}x 20-day average volume of {int(vol_avg):,})."
            )

            scored_setups.append({
                "_rank_score": conviction_raw,
                "symbol": sym,
                "display_label": it.get("display_label", sym),
                "sector": sec_info["sector"],
                "trade_date": it["latest_date"],
                "setup_type": setup_type,
                "direction": "BUY / LONG" if is_bullish else "SHORT CANDIDATE — VERIFY CONTRACT",
                "setup_grade": grade,
                "setup_score": prob_pct,
                "score_interpretation": "Rule strength /100, not a probability, backtest result, or execution approval.",
                "trade_plan": plan,
                "history_coverage": {"first_date": it["first_date"], "latest_date": it["latest_date"], "bars_count": it["bars_count"]},
                "background_status": "Fundamentals unavailable.",
                "composite_score": f"{score:+d}/9",
                "current_price": round(c_price, 2),
                "change_pct": round(float(it.get("change_pct") or 0.0), 2),
                "entry_price": entry_price,
                "target_1": target_1,
                "target_2": target_2,
                "stop_loss": stop_loss,
                "risk_per_share": round(risk, 2),
                "risk_reward_t1": f"{rr_t1:.2f} : 1",
                "risk_reward_t2": f"{rr_t2:.2f} : 1",
                "rsi14": round(rsi, 1),
                "adx14": round(adx, 1),
                "volume_ratio": round(vol_ratio, 2),
                "trend_state": trend_state,
                "momentum_state": momentum_state,
                "weekly_pivot_p": round(float(wp.get("P") or 0.0), 2),
                "invalidation": invalidation,
                "technical_why": tech_reasons,
                "fundamental_why": liq_notes,
            })

        scored_setups.sort(key=lambda x: x["_rank_score"], reverse=True)
        top_setups = scored_setups[:limit]
        for idx, st in enumerate(top_setups, start=1):
            st.pop("_rank_score", None)
            st["rank"] = idx

        target_label = custom_query.strip().upper() or scope_or_sector

        return {
            "target_label": target_label,
            "market_latest_date": market_date,
            "candidates_scanned": counts["analyzed"],
            "scan_counts": dict(counts, displayed=len(top_setups)),
            "diagnostics": diagnostics,
            "outside_scope": outside_scope,
            "query_interpretation": "Exact stored ticker" if exact_query else "Case-insensitive ticker/sector text",
            "scope_note": "Scope and query are intersected. Direction is applied after examining the matched history. Use All imported cash symbols to search outside a watchlist.",
            "message": ("No cash symbols matched this scope/query. Check the coverage tab; reference membership, futures and account trades are not cash OHLCV." if not counts["matched"] else "Every matched symbol is accounted for below, including data-readiness and direction exclusions."),
            "setups_count": len(top_setups),
            "screening_note": "Only current imported-session, positive-volume candidates with a valid structural plan and gross R/R >= 1.5 are returned. Fewer than five or zero is valid. Rule scores are not win probabilities.",
            "setups": top_setups,
            "rejected": sorted(rejected, key=lambda r: (-abs(r["score"]), r["symbol"])),
        }

    @persisted_result
    def run_automated_technical_analyst(
        self,
        symbol: str = "ATRL",
        intended_action: str = "Evaluate Buy / Hold / Sell",
    ) -> Dict[str, Any]:
        """
        Card 2: Automated Technical Analyst.
        Analyzes [action/ticker] using daily and weekly charts, breaking down:
          1. Support/resistance levels (Daily Classic/Fib/Camarilla + Weekly + Swing High/Low)
          2. Trend lines (20-day linear regression channel slope, upper/lower channel boundaries)
          3. Moving averages (EMA 9, 21, 50, 200 + SMA 20, 50 + Weekly SMA 4 & 10)
          4. Momentum & volatility indicators (Wilder RSI 14, MACD, Bollinger %B/Width, ADX +DI/-DI, VWAP)
          5. Step-by-step trading signal (Buy/Hold/Sell/Short Sell) with justification.
        """
        from psx_app.services.data_guard import date_integrity
        integrity = date_integrity(self.db_path)
        if not integrity["ok"]:
            return {"symbol": symbol, "status": "BLOCKED", "message": integrity["message"], "date_integrity": integrity}
        sym = self.tech_service.resolve_ticker(symbol)
        t_data = self.tech_service.get_ticker_analysis(sym, tail_bars=0)
        lat = t_data["latest"]
        series = t_data["series"]

        if not lat or not series:
            return {
                "symbol": sym,
                "status": "NO_DATA",
                "message": f"No historical OHLCV records found for '{sym}'.",
            }

        if lat["signal"]["combined_signal"] == "INSUFFICIENT DATA":
            return {"symbol": sym, "status": "INSUFFICIENT_DATA", "latest": lat,
                    "message": f"{sym}: {lat['bars_count']} cash sessions stored from {lat['first_date']} through {lat['latest_date']}. Available indicators are insufficient for a multi-indicator signal (minimum 26 sessions). Missing indicators are unavailable, not zero."}

        def shown(value, decimals=2, signed=False):
            if value is None: return "N/A"
            return format(value, ("+" if signed else "") + f".{decimals}f")

        # 1. Build Weekly Chart Candles from Daily Bars
        weeks_map: Dict[str, Dict[str, Any]] = {}
        week_keys: List[str] = []
        for b in series:
            dt = datetime.strptime(b["trade_date"], "%Y-%m-%d")
            iy, iw, _ = dt.isocalendar()
            wk = f"{iy}-W{iw:02d}"
            if wk not in weeks_map:
                weeks_map[wk] = {
                    "week_key": wk,
                    "start_date": b["trade_date"],
                    "end_date": b["trade_date"],
                    "open": b["open"],
                    "high": b["high"],
                    "low": b["low"],
                    "close": b["close"],
                    "volume": b["volume"],
                    "sessions": 1,
                }
                week_keys.append(wk)
            else:
                w_obj = weeks_map[wk]
                w_obj["end_date"] = b["trade_date"]
                w_obj["high"] = max(w_obj["high"], b["high"])
                w_obj["low"] = min(w_obj["low"], b["low"])
                w_obj["close"] = b["close"]
                w_obj["volume"] += b["volume"]
                w_obj["sessions"] += 1

        weekly_candles = [weeks_map[k] for k in week_keys]
        # Never call an unfinished current week a confirmed weekly signal.
        unfinished_week_excluded = datetime.strptime(series[-1]["trade_date"], "%Y-%m-%d").weekday() < 4
        if unfinished_week_excluded:
            weekly_candles = weekly_candles[:-1]
        w_closes = [w["close"] for w in weekly_candles]
        w_sma4 = sum(w_closes[-4:]) / 4 if len(w_closes) >= 4 else None
        w_sma10 = sum(w_closes[-10:]) / 10 if len(w_closes) >= 10 else None
        w_chg_4w = ((w_closes[-1] - w_closes[-min(5, len(w_closes))]) / w_closes[-min(5, len(w_closes))] * 100.0) if len(w_closes) >= 5 else None
        weekly_trend = "INSUFFICIENT COMPLETED WEEKS (<10)"
        if len(w_closes) >= 10:
            weekly_trend = "BULLISH (Above 4W & 10W SMA)" if (w_closes[-1] >= w_sma4 and w_sma4 >= w_sma10) else (
                "BEARISH (Below 4W & 10W SMA)" if (w_closes[-1] < w_sma4 and w_sma4 < w_sma10) else "CONSOLIDATING / TRANSITIONAL")

        # 2. Compute 20-Session Linear Regression Trend Line & Channel
        tail20 = series[-min(20, len(series)):]
        n20 = len(tail20)
        xs = list(range(n20))
        ys = [float(b["close"]) for b in tail20]
        x_mean = sum(xs) / float(n20)
        y_mean = sum(ys) / float(n20)
        denom = sum((x - x_mean) ** 2 for x in xs) or 1.0
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
        intercept = y_mean - slope * x_mean
        reg_now = intercept + slope * (n20 - 1)
        residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
        res_std = math.sqrt(sum(r * r for r in residuals) / float(n20))
        upper_trendline = reg_now + 1.5 * res_std
        lower_trendline = reg_now - 1.5 * res_std
        swing_high_20 = max(float(b["high"]) for b in tail20)
        swing_low_20 = min(float(b["low"]) for b in tail20)

        # 3. Moving Averages Breakdown
        c_val = float(lat["close"])
        ma_list = []
        for lbl, val in [
            ("EMA 9 (Fast)", lat.get("ema9")),
            ("EMA 21 (Pullback)", lat.get("ema21")),
            ("SMA 20 (Bollinger Mid)", lat.get("sma20")),
            ("EMA 50 (Medium Trend)", lat.get("ema50")),
            ("SMA 50", lat.get("sma50")),
            ("EMA 200 (Strict)", lat.get("ema200")),
            ("Weekly SMA 4 (~1 Month)", w_sma4),
            ("Weekly SMA 10 (~1 Quarter)", w_sma10),
        ]:
            if val is not None and val > 0:
                dist_pct = (c_val - val) / val * 100.0
                ma_list.append({
                    "name": lbl,
                    "value": round(val, 2),
                    "distance_pct": round(dist_pct, 2),
                    "status": "BULLISH (Price Above)" if c_val >= val else "BEARISH (Price Below)",
                })

        # 4. Step-by-Step Signal & Justification
        sig = lat["signal"]
        dp = lat["daily_pivots"]["classic"]
        wp = (lat.get("weekly_pivots") or {}).get("pivots") or {}
        sec_info = self.sector_map.get(sym, {
            "sector": "PSX Listed Equity",
            "fundamental": "Fundamentals unavailable; no verified financial/news input supplied.",
        })

        steps = [
            {
                "step": "Step 1 • Daily & Weekly Multi-Timeframe Chart Structure",
                "verdict": weekly_trend,
                "detail": (
                    f"On the Daily chart ({lat['latest_date']}), {sym} closed at {c_val:.2f} PKR ({lat['change_pct']:+.2f}%). "
                    f"Completed-week context ({len(weekly_candles)} weeks; through {weekly_candles[-1]['end_date'] if weekly_candles else 'N/A'}): completed-week close change {shown(w_chg_4w, signed=True)}% over 4 weeks; SMA(4)={shown(w_sma4)}, SMA(10)={shown(w_sma10)}. This can differ from the latest daily close."
                ),
            },
            {
                "step": "Step 2 • Support, Resistance & Trend Line Breakdown",
                "verdict": "ABOVE DAILY PIVOT" if c_val >= dp["P"] else "BELOW DAILY PIVOT",
                "detail": (
                    f"20-Session Linear Regression Trend Line slope is {slope:+.2f} PKR/day (Center={reg_now:.2f}, Upper Channel Resistance={upper_trendline:.2f}, Lower Channel Support={lower_trendline:.2f}). "
                    f"Immediate Resistance: R1={dp['R1']:.2f}, R2={dp['R2']:.2f}, 20D High={swing_high_20:.2f}. "
                    f"Immediate Support: Pivot P={dp['P']:.2f}, S1={dp['S1']:.2f}, S2={dp['S2']:.2f}, 20D Low={swing_low_20:.2f}."
                ),
            },
            {
                "step": "Step 3 • Moving Averages Alignment",
                "verdict": f"{sum(1 for m in ma_list if 'Above' in m['status'])}/{len(ma_list)} MAs Bullish",
                "detail": (
                    f"EMA(9)={shown(lat.get('ema9'))}, EMA(21)={shown(lat.get('ema21'))}, EMA(50)={shown(lat.get('ema50'))}, "
                    f"SMA(20)={shown(lat.get('sma20'))}. "
                    + (
                        "Bullish short-to-medium EMA stack (EMA 9 > EMA 21 > EMA 50)."
                        if all(lat.get(k) is not None for k in ("ema9", "ema21", "ema50")) and lat["ema9"] >= lat["ema21"] >= lat["ema50"]
                        else ("EMA stack unavailable: not all EMA periods initialized." if any(lat.get(k) is None for k in ("ema9", "ema21", "ema50")) else "Mixed/consolidating moving average alignment; monitor EMA 21 as pivot trigger.")
                    )
                ),
            },
            {
                "step": "Step 4 • Momentum, Volatility & Volume Confirmation",
                "verdict": f"RSI {shown(lat.get('rsi14'), 1)} ({lat['rsi_zone']}) | ADX {shown(lat.get('adx14'), 1)}",
                "detail": (
                    f"Wilder RSI(14)={shown(lat.get('rsi14'))} (YTD range {shown(lat['rsi_ytd_low']['value'], 1)}–{shown(lat['rsi_ytd_high']['value'], 1)}). "
                    f"MACD(12,26,9)={shown(lat.get('macd'))} vs Signal {shown(lat.get('macd_sig'))} (Hist {shown(lat.get('macd_hist'), signed=True)}). "
                    f"Bollinger %B={shown(lat['pct_b']*100 if lat.get('pct_b') is not None else None, 1)}%, ADX(14)={shown(lat.get('adx14'))} (+DI={shown(lat.get('plus_di'), 1)}, -DI={shown(lat.get('minus_di'), 1)})."
                ),
            },
            {
                "step": f"Step 5 • Final Step-by-Step Signal ({sig['combined_signal']}) & Execution Plan",
                "verdict": f"{sig['combined_signal']} (Score {sig['score']:+d}/9)",
                "detail": (
                    f"For requested action '{intended_action}': System issues '{sig['combined_signal']}' with {sig['confidence']} rule strength (not a probability). "
                    f"Entry Reference: {sig['entry_reference']} PKR | Stop-Loss Reference: {sig['stop_loss_reference']} PKR | "
                    f"Target Reference: {sig['target_reference']} PKR (R/R: {sig['risk_reward']}x). Invalidation: {sig['invalidation']}"
                ),
            },
        ]

        bullish_mas = sum(1 for m in ma_list if "Above" in m["status"])
        macd_h2 = float(lat.get("macd_hist") or 0.0)
        structure_snapshot = {
            "weekly_trend": weekly_trend,
            "price_vs_daily_pivot": "ABOVE Daily Pivot" if c_val >= dp["P"] else "BELOW Daily Pivot",
            "ma_alignment": f"{bullish_mas}/{len(ma_list)} MAs Bullish",
            "rsi_zone": f"RSI {shown(lat.get('rsi14'), 1)} — {lat['rsi_zone']}",
            "adx_strength": f"ADX {shown(lat.get('adx14'), 1)} ({'Unavailable' if lat.get('adx14') is None else 'Trending' if lat['adx14'] >= 20 else 'Weak/Range'})",
            "macd_momentum": "Unavailable (MACD signal not initialized)" if lat.get("macd_hist") is None else f"{'Rising' if macd_h2 > 0 else 'Fading'} (Hist {macd_h2:+.3f})",
        }

        key_levels = {
            "daily_pivot": round(float(dp["P"]), 2),
            "r1": round(float(dp["R1"]), 2),
            "r2": round(float(dp["R2"]), 2),
            "r3": round(float(dp["R3"]), 2) if dp.get("R3") is not None else None,
            "s1": round(float(dp["S1"]), 2),
            "s2": round(float(dp["S2"]), 2),
            "s3": round(float(dp["S3"]), 2) if dp.get("S3") is not None else None,
            "weekly_pivot": round(float(wp["P"]), 2) if wp.get("P") is not None else None,
            "swing_high_20d": round(swing_high_20, 2),
            "swing_low_20d": round(swing_low_20, 2),
            "regression_center": round(reg_now, 2),
            "upper_channel": round(upper_trendline, 2),
            "lower_channel": round(lower_trendline, 2),
        }

        return {
            "symbol": sym,
            "display_label": t_data.get("display_label", sym),
            "sector": sec_info["sector"],
            "fundamental_summary": "Fundamentals unavailable: no verified financial statements or current news supplied.",
            "intended_action": intended_action,
            "structure_snapshot": structure_snapshot,
            "key_levels": key_levels,
            "latest": lat,
            "trend_line": {
                "period_days": n20,
                "slope_pkr_per_day": round(slope, 3),
                "regression_center": round(reg_now, 2),
                "upper_channel_resistance": round(upper_trendline, 2),
                "lower_channel_support": round(lower_trendline, 2),
                "swing_high_20d": round(swing_high_20, 2),
                "swing_low_20d": round(swing_low_20, 2),
            },
            "weekly_summary": {
                "weeks_count": len(weekly_candles),
                "last_completed_week_end": weekly_candles[-1]["end_date"] if weekly_candles else None,
                "unfinished_week_excluded": unfinished_week_excluded,
                "method": "Completed imported weeks; no exchange holiday calendar is available. Unfinished latest week is excluded conservatively.",
                "weekly_sma4": round(w_sma4, 2) if w_sma4 is not None else None,
                "weekly_sma10": round(w_sma10, 2) if w_sma10 is not None else None,
                "change_4w_pct": round(w_chg_4w, 2) if w_chg_4w is not None else None,
                "weekly_trend": weekly_trend,
                "recent_weeks": weekly_candles[-8:],
            },
            "moving_averages_matrix": ma_list,
            "step_by_step_analysis": steps,
        }
