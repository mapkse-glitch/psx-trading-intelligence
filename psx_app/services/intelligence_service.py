import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import CORE_36_TICKERS
from psx_app.database.schema import get_connection
from psx_app.services.technical_service import TechnicalService

PSX_SECTOR_MAP: Dict[str, Dict[str, str]] = {
    "OGDC": {
        "sector": "Oil & Gas Exploration",
        "fundamental": "Strong gas tariff reforms improving circular debt cash collections, high dividend yield, and E&P reserve replacement tailwinds.",
    },
    "PPL": {
        "sector": "Oil & Gas Exploration",
        "fundamental": "Improved Sui/Kandhkot receivables recovery following energy tariff adjustments and active frontier exploration.",
    },
    "PSO": {
        "sector": "Oil & Gas Marketing & Refinery",
        "fundamental": "Market-leading OMC retail volume share, declining finance costs from monetary easing, and LNG receivable settlement progress.",
    },
    "ATRL": {
        "sector": "Oil & Gas Marketing & Refinery",
        "fundamental": "Healthy gross refining margins (GRMs), high distillate share, debt-free balance sheet, and Brownfield Refinery Policy upgrade optionality.",
    },
    "NRL": {
        "sector": "Oil & Gas Marketing & Refinery",
        "fundamental": "Lube base-oil margin recovery, fuel oil export economics, and lower working-capital borrowing rates.",
    },
    "PRL": {
        "sector": "Oil & Gas Marketing & Refinery",
        "fundamental": "High operational throughput leverage to regional cracks and refinery policy incentives.",
    },
    "SNGP": {
        "sector": "Oil & Gas Marketing & Refinery",
        "fundamental": "Unaccounted-for-Gas (UFG) control below regulatory benchmarks and WACC-linked regulated asset base returns.",
    },
    "SSGC": {
        "sector": "Oil & Gas Marketing & Refinery",
        "fundamental": "Ongoing rehabilitation lowers UFG losses alongside revised OGRA revenue requirements.",
    },
    "LUCK": {
        "sector": "Cement & Construction",
        "fundamental": "Lowest-cost cement producer in Pakistan with diversified earnings from Lucky Electric, Lucky Core Industries, and regional clinker exports.",
    },
    "MLCF": {
        "sector": "Cement & Construction",
        "fundamental": "Internal power generation efficiency (coal/solar/WHR), strong domestic Northern zone pricing discipline, and deleveraging benefit.",
    },
    "DGKC": {
        "sector": "Cement & Construction",
        "fundamental": "High financial leverage to SBP interest-rate cuts and Southern hub export access via Hub plant.",
    },
    "THCCL": {
        "sector": "Cement & Construction",
        "fundamental": "Southern zone retention price stability and strong free-cash-flow generation.",
    },
    "UBL": {
        "sector": "Commercial Banking",
        "fundamental": "Tier-1 ROE leadership, high current-account deposit mix, sovereign PIB portfolio capital gains, and premier cash dividend payout.",
    },
    "HBL": {
        "sector": "Commercial Banking",
        "fundamental": "Largest domestic deposit franchise, expanding agricultural & SME credit book, and digital banking scale.",
    },
    "NBP": {
        "sector": "Commercial Banking",
        "fundamental": "Balance-sheet re-rating post pension litigation clarity and strong treasury income.",
    },
    "BOP": {
        "sector": "Commercial Banking",
        "fundamental": "Deep discount to book value with expanding public-sector and Punjab commercial lending volumes.",
    },
    "FFC": {
        "sector": "Fertilizer & Chemicals",
        "fundamental": "Consistent urea offtake resilience, post-merger scale synergies, and blue-chip dividend yield stability.",
    },
    "ENGROH": {
        "sector": "Fertilizer & Chemicals",
        "fundamental": "Conglomerate holding value across fertilizers, petrochemicals, telecom towers, and energy terminals.",
    },
    "HUBC": {
        "sector": "Power Generation & Utilities",
        "fundamental": "Diversified cash flows from Thar coal power (TEL/TNPTL), CPEC energy assets, and BYD electric-vehicle assembly venture.",
    },
    "NCPL": {
        "sector": "Power Generation & Utilities",
        "fundamental": "High liquidity and tariff settlement cash payouts supporting yield.",
    },
    "NPL": {
        "sector": "Power Generation & Utilities",
        "fundamental": "Strong balance sheet liquidity and consistent dividend distribution record.",
    },
    "SYS": {
        "sector": "Technology & IT Exports",
        "fundamental": "Structural USD/GCC IT software export growth, enterprise cloud/AI transformation contracts, and zero domestic circular-debt exposure.",
    },
    "TRG": {
        "sector": "Technology & IT Exports",
        "fundamental": "High-beta technology & BPO portfolio valuation sensitivity and liquid futures trading participation.",
    },
    "NETSOL": {
        "sector": "Technology & IT Exports",
        "fundamental": "Global auto-finance SaaS (NFS Ascent) recurring subscription revenue in North America, Europe, and Asia-Pacific.",
    },
    "PTC": {
        "sector": "Telecom & Exchange",
        "fundamental": "ARPU expansion in broadband/fiber, Telenor Pakistan acquisition synergies, and lower KIBOR interest expense on debt.",
    },
    "PSX": {
        "sector": "Telecom & Exchange",
        "fundamental": "Direct operational leverage to rising Pakistan Stock Exchange daily traded value, new listings, and investor participation.",
    },
    "SAZEW": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Surging Haval SUV / HEV hybrid sales volume, strong cash margins, and new energy vehicle expansion.",
    },
    "GAL": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Commercial truck/bus fleet replacement demand and Chery crossover localization.",
    },
    "GHNI": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Isuzu commercial vehicle volume recovery as logistics and trade activity rebound.",
    },
    "PAEL": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Power transformer/switchgear grid orders and consumer appliance demand recovery under lower financing rates.",
    },
    "MUGHAL": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Long steel rebar demand sensitivity to construction revival and non-ferrous copper export revenues.",
    },
    "ISL": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Flat steel (CRC/HDGC) market leader benefiting from auto/appliance recovery and lower finance charges.",
    },
    "INIL": {
        "sector": "Automobiles & Engineering",
        "fundamental": "Steel pipe/polymer exports and majority stake in International Steels (ISL).",
    },
    "SEARL": {
        "sector": "Pharmaceuticals & Healthcare",
        "fundamental": "Deregulation of non-essential drug prices restoring gross margins alongside lower finance costs post debt restructuring.",
    },
    "CPHL": {
        "sector": "Pharmaceuticals & Healthcare",
        "fundamental": "API and formulation volume growth with margin expansion following CPI-linked and non-essential drug pricing flexibility.",
    },
    "NML": {
        "sector": "Textiles & Conglomerate",
        "fundamental": "Value-added textile export recovery plus substantial portfolio dividend income from MCB, Lalpir, and Nishat group companies.",
    },
}


class IntelligenceService:
    """
    Powers the two interactive institutional intelligence cards:
      1. Trading Ideas Generator (Top 5 High-Probability Setups with Entry, Targets, Stop-Loss, R/R, Technical & Fundamental Why)
      2. Automated Technical Analyst (Daily & Weekly Chart Analysis, S/R, Trend Lines, Moving Averages, Momentum & Step-by-Step Signal)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.tech_service = TechnicalService(db_path)

    def get_available_sectors_and_filters(self) -> Dict[str, Any]:
        sectors = sorted({v["sector"] for v in PSX_SECTOR_MAP.values()})
        return {
            "presets": [
                {"id": "CORE36", "label": "Core 36 Institutional Watchlist"},
                {"id": "TOP5_VOL", "label": "Top 5 Volume Register Leaders (23 Tickers)"},
                {"id": "FUTURES", "label": "Deliverable Futures Eligible Universe"},
                {"id": "ALL_MARKET", "label": "All PSX Cash Equities (531 Tickers)"},
            ],
            "sectors": sectors,
            "core_tickers": CORE_36_TICKERS,
        }

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
        uni_scope = "all" if (scope_or_sector == "ALL_MARKET" or custom_query.strip()) else "core36"
        uni = self.tech_service.get_universe_summary(scope=uni_scope)
        items = uni["items"]

        # Enrich with Top 5 Volume Register & Futures spread context from DB
        with get_connection(self.db_path) as c:
            top5_tickers = {(r["ticker"], r["trade_date"]): r["top_vol"] for r in c.execute(
                "SELECT ticker, trade_date, SUM(volume) AS top_vol FROM top5_volume_records GROUP BY ticker, trade_date").fetchall()}
            fut_map = {}
            for row in c.execute("SELECT base_symbol, trade_date, close, contract_symbol, volume FROM futures_ohlcv ORDER BY volume DESC, contract_symbol ASC"):
                fut_map.setdefault((row["base_symbol"], row["trade_date"]), dict(row))

        q_clean = self.tech_service.resolve_ticker(custom_query.strip()) if custom_query.strip() else ""
        filtered: List[Dict[str, Any]] = []

        for it in items:
            sym = it["symbol"]
            sec_info = PSX_SECTOR_MAP.get(sym, {
                "sector": "PSX Listed Equity",
                "fundamental": "Active PSX equity with institutional price-volume participation and technical structure.",
            })
            if q_clean:
                if q_clean not in sym and q_clean not in sec_info["sector"].upper():
                    continue
            elif scope_or_sector == "TOP5_VOL":
                if (sym, it["latest_date"]) not in top5_tickers:
                    continue
            elif scope_or_sector == "FUTURES":
                if not it.get("is_futures_eligible"):
                    continue
            elif scope_or_sector not in ("CORE36", "ALL_MARKET"):
                if sec_info["sector"].lower() != scope_or_sector.lower():
                    continue

            if it["bars_count"] < 26 or it.get("rsi14") is None:
                continue

            sig_score = it["signal"]["score"]
            act = it["signal"]["combined_signal"].upper()

            if direction_filter == "LONG" and sig_score < 1:
                continue
            if direction_filter == "SHORT" and sig_score > -1:
                continue

            filtered.append(it)

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

            is_bullish = score >= 0
            if direction_filter == "SHORT":
                is_bullish = False
            elif direction_filter == "LONG":
                is_bullish = True

            if is_bullish:
                setup_type = "LONG / MOMENTUM BREAKOUT" if c_price >= p else "LONG / PULLBACK TO SUPPORT"
                entry_price = round(c_price if c_price >= p else max(s1, p * 0.995), 2)
                stop_loss = round(min(s1, e21 * 0.985), 2)
                if stop_loss >= entry_price:
                    stop_loss = round(entry_price * 0.965, 2)
                risk = max(entry_price - stop_loss, entry_price * 0.015)
                target_1 = round(max(r1, entry_price + risk * 1.6), 2)
                target_2 = round(max(r2, entry_price + risk * 2.6), 2)
            else:
                setup_type = (
                    "SHORT SELL (FUTURES) / BREAKDOWN"
                    if it.get("is_futures_eligible")
                    else "TACTICAL SELL / RESISTANCE REJECTION"
                )
                entry_price = round(c_price if c_price <= p else min(r1, p * 1.005), 2)
                stop_loss = round(max(r1, e21 * 1.015), 2)
                if stop_loss <= entry_price:
                    stop_loss = round(entry_price * 1.035, 2)
                risk = max(stop_loss - entry_price, entry_price * 0.015)
                target_1 = round(min(s1, entry_price - risk * 1.6), 2)
                target_2 = round(min(s2, entry_price - risk * 2.6), 2)

            reward_t1 = abs(target_1 - entry_price)
            reward_t2 = abs(target_2 - entry_price)
            rr_t1 = round(reward_t1 / risk, 2) if risk > 0 else 1.5
            rr_t2 = round(reward_t2 / risk, 2) if risk > 0 else 2.5

            # Conviction ranking metric (deterministic)
            dir_alignment = score if is_bullish else -score
            conviction_raw = (
                dir_alignment * 8.5
                + min(adx, 45.0) * 0.45
                + min(vol_ratio, 3.0) * 6.0
                + (5.0 if (sym, it["latest_date"]) in top5_tickers else 0.0)
                + min(rr_t2, 4.0) * 3.0
            )
            prob_pct = min(94, max(58, int(round(55 + conviction_raw * 0.42))))
            grade = "A+" if prob_pct >= 84 else ("A" if prob_pct >= 75 else "B+")

            sec_info = PSX_SECTOR_MAP.get(sym, {
                "sector": "PSX Listed Equity",
                "fundamental": "Active PSX equity with institutional price-volume participation.",
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

            liq_notes = ["Unverified static background (not a current finding): " + sec_info["fundamental"]]
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
                "direction": "BUY / LONG" if is_bullish else ("SHORT SELL" if it.get("is_futures_eligible") else "SELL"),
                "setup_grade": grade,
                "setup_score": prob_pct,
                "score_interpretation": "Deterministic rule score, not a probability of profit.",
                "background_status": "Unverified static background; not current fundamental research.",
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
            "candidates_scanned": len(filtered),
            "setups_count": len(top_setups),
            "setups": top_setups,
        }

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
        t_data = self.tech_service.get_ticker_analysis(sym, tail_bars=200)
        lat = t_data["latest"]
        series = t_data["series"]

        if not lat or not series:
            return {
                "symbol": sym,
                "status": "NO_DATA",
                "message": f"No historical OHLCV records found for '{sym}'.",
            }

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
        w_closes = [w["close"] for w in weekly_candles]
        w_sma4 = sum(w_closes[-4:]) / min(4, len(w_closes))
        w_sma10 = sum(w_closes[-10:]) / min(10, len(w_closes))
        w_chg_4w = ((w_closes[-1] - w_closes[-min(5, len(w_closes))]) / w_closes[-min(5, len(w_closes))] * 100.0) if len(w_closes) >= 2 else 0.0
        weekly_trend = "BULLISH (Above 4W & 10W SMA)" if (w_closes[-1] >= w_sma4 and w_sma4 >= w_sma10) else (
            "BEARISH (Below 4W & 10W SMA)" if (w_closes[-1] < w_sma4 and w_sma4 < w_sma10) else "CONSOLIDATING / TRANSITIONAL"
        )

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
            ("EMA 200 (Recursive Warm-Up)", lat.get("ema200_recursive")),
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
        sec_info = PSX_SECTOR_MAP.get(sym, {
            "sector": "PSX Listed Equity",
            "fundamental": "Active PSX equity with institutional price-volume participation.",
        })

        steps = [
            {
                "step": "Step 1 • Daily & Weekly Multi-Timeframe Chart Structure",
                "verdict": weekly_trend,
                "detail": (
                    f"On the Daily chart ({lat['latest_date']}), {sym} closed at {c_val:.2f} PKR ({lat['change_pct']:+.2f}%). "
                    f"On the Weekly chart ({len(weekly_candles)} weeks), price is {w_chg_4w:+.2f}% over 4 weeks with Weekly SMA(4)={w_sma4:.2f} and Weekly SMA(10)={w_sma10:.2f}."
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
                    f"EMA(9)={lat.get('ema9') or 0:.2f}, EMA(21)={lat.get('ema21') or 0:.2f}, EMA(50)={lat.get('ema50') or 0:.2f}, "
                    f"SMA(20)={lat.get('sma20') or 0:.2f}. "
                    + (
                        "Bullish short-to-medium EMA stack (EMA 9 > EMA 21 > EMA 50)."
                        if (lat.get("ema9") or 0) >= (lat.get("ema21") or 0) >= (lat.get("ema50") or 0)
                        else "Mixed/consolidating moving average alignment; monitor EMA 21 as pivot trigger."
                    )
                ),
            },
            {
                "step": "Step 4 • Momentum, Volatility & Volume Confirmation",
                "verdict": f"RSI {lat.get('rsi14') or 0:.1f} ({lat['rsi_zone']}) | ADX {lat.get('adx14') or 0:.1f}",
                "detail": (
                    f"Wilder RSI(14)={lat.get('rsi14') or 0:.2f} (YTD range {lat['rsi_ytd_low']['value'] or 0:.1f}–{lat['rsi_ytd_high']['value'] or 0:.1f}). "
                    f"MACD(12,26,9)={lat.get('macd') or 0:.2f} vs Signal {lat.get('macd_sig') or 0:.2f} (Hist {lat.get('macd_hist') or 0:+.2f}). "
                    f"Bollinger %B={(lat.get('pct_b') or 0)*100:.1f}%, ADX(14)={lat.get('adx14') or 0:.2f} (+DI={lat.get('plus_di') or 0:.1f}, -DI={lat.get('minus_di') or 0:.1f})."
                ),
            },
            {
                "step": f"Step 5 • Final Step-by-Step Signal ({sig['combined_signal']}) & Execution Plan",
                "verdict": f"{sig['combined_signal']} (Score {sig['score']:+d}/9)",
                "detail": (
                    f"For requested action '{intended_action}': System issues '{sig['combined_signal']}' with {sig['confidence']} confidence. "
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
            "rsi_zone": f"RSI {float(lat.get('rsi14') or 0):.1f} — {lat['rsi_zone']}",
            "adx_strength": f"ADX {float(lat.get('adx14') or 0):.1f} ({'Trending' if float(lat.get('adx14') or 0) >= 20 else 'Weak/Range'})",
            "macd_momentum": f"{'Rising' if macd_h2 > 0 else 'Fading'} (Hist {macd_h2:+.3f})",
        }

        key_levels = {
            "daily_pivot": round(float(dp["P"]), 2),
            "r1": round(float(dp["R1"]), 2),
            "r2": round(float(dp["R2"]), 2),
            "r3": round(float(dp["R3"]), 2) if dp.get("R3") is not None else None,
            "s1": round(float(dp["S1"]), 2),
            "s2": round(float(dp["S2"]), 2),
            "s3": round(float(dp["S3"]), 2) if dp.get("S3") is not None else None,
            "weekly_pivot": round(float(wp.get("P") or 0.0), 2),
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
            "fundamental_summary": "Unverified static background (not current research): " + sec_info["fundamental"],
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
                "weekly_sma4": round(w_sma4, 2),
                "weekly_sma10": round(w_sma10, 2),
                "change_4w_pct": round(w_chg_4w, 2),
                "weekly_trend": weekly_trend,
                "recent_weeks": weekly_candles[-8:],
            },
            "moving_averages_matrix": ma_list,
            "step_by_step_analysis": steps,
        }
