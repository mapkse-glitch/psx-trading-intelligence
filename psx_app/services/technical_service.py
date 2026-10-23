import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import CORE_36_TICKERS, TICKER_ALIASES
from psx_app.database.repository import Repository
from psx_app.database.schema import get_connection


class TechnicalService:
    """
    Module D — Technical Analysis & 36-Ticker (+ 531 Universe) Engine.
    Calculates Wilder's RSI(14), MACD(12,26,9), Bollinger Bands(20,2),
    EMA 9/21/50/200, Daily Typical-Price & 20D Rolling VWAP Proxy,
    ADX(14) (+DI/-DI), Daily Pivots (Classic, Fibonacci, Camarilla),
    Weekly Pivots (previous completed trading week), and an Explainable Signal Engine.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.repo = Repository(db_path)

    @staticmethod
    def resolve_ticker(symbol: str) -> str:
        s = symbol.strip().upper()
        return TICKER_ALIASES.get(s, s)

    @staticmethod
    def compute_classic_fib_camarilla_pivots(high: float, low: float, close: float) -> Dict[str, Any]:
        rng = high - low
        p = (high + low + close) / 3.0
        classic = {
            "P": p,
            "R1": 2.0 * p - low,
            "R2": p + rng,
            "R3": high + 2.0 * (p - low),
            "S1": 2.0 * p - high,
            "S2": p - rng,
            "S3": low - 2.0 * (high - p),
        }
        fibonacci = {
            "P": p,
            "R1": p + 0.382 * rng,
            "R2": p + 0.618 * rng,
            "R3": p + 1.000 * rng,
            "S1": p - 0.382 * rng,
            "S2": p - 0.618 * rng,
            "S3": p - 1.000 * rng,
        }
        camarilla = {
            "P": p,
            "R1": close + rng * 1.1 / 12.0,
            "R2": close + rng * 1.1 / 6.0,
            "R3": close + rng * 1.1 / 4.0,
            "R4": close + rng * 1.1 / 2.0,
            "S1": close - rng * 1.1 / 12.0,
            "S2": close - rng * 1.1 / 6.0,
            "S3": close - rng * 1.1 / 4.0,
            "S4": close - rng * 1.1 / 2.0,
        }
        return {"classic": classic, "fibonacci": fibonacci, "camarilla": camarilla}

    @classmethod
    def compute_weekly_pivots(cls, bars: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute weekly pivots from the latest completed trading week.
        If the latest week in `bars` has >= 5 trading sessions (Mon-Fri completed), use it;
        otherwise use the immediately preceding completed week.
        """
        if not bars:
            return {"status": "N/A", "week_label": None, "pivots": None}

        weeks: Dict[str, List[Dict[str, Any]]] = {}
        week_order: List[str] = []
        for b in bars:
            dt = datetime.strptime(b["trade_date"], "%Y-%m-%d")
            iso_y, iso_w, _ = dt.isocalendar()
            wk_key = f"{iso_y}-W{iso_w:02d}"
            if wk_key not in weeks:
                weeks[wk_key] = []
                week_order.append(wk_key)
            weeks[wk_key].append(b)

        latest_wk = week_order[-1]
        latest_wk_bars = weeks[latest_wk]
        last_dt = datetime.strptime(latest_wk_bars[-1]["trade_date"], "%Y-%m-%d")

        # A PSX trading week is complete if its last trading day is Friday (weekday==4) or if it's the only week
        if last_dt.weekday() >= 4 or len(week_order) == 1:
            target_wk = latest_wk
        else:
            target_wk = week_order[-2]

        w_bars = weeks[target_wk]
        valid_bars = [b for b in w_bars if (b.get("high") or 0) > 0 and (b.get("low") or 0) > 0]
        if not valid_bars:
            valid_bars = w_bars

        w_high = max(float(b["high"] if (b.get("high") or 0) > 0 else b["close"]) for b in valid_bars)
        w_low = min(float(b["low"] if (b.get("low") or 0) > 0 else b["close"]) for b in valid_bars)
        w_close = float(valid_bars[-1]["close"])
        piv = cls.compute_classic_fib_camarilla_pivots(w_high, w_low, w_close)["classic"]

        return {
            "status": "OK",
            "week_key": target_wk,
            "start_date": w_bars[0]["trade_date"],
            "end_date": w_bars[-1]["trade_date"],
            "sessions_in_week": len(w_bars),
            "high": w_high,
            "low": w_low,
            "close": w_close,
            "pivots": piv,
        }

    def calculate_series_for_bars(
        self,
        symbol: str,
        bars: List[Dict[str, Any]],
        settings: Optional[Dict[str, Any]] = None,
        is_futures_eligible: bool = True,
    ) -> Dict[str, Any]:
        """
        Pure, deterministic, lookahead-free indicator calculation over chronological daily OHLCV bars.
        """
        cfg = settings or self.repo.get_settings()
        rsi_p = int(cfg.get("rsi_period", 14))
        macd_fast = int(cfg.get("macd_fast", 12))
        macd_slow = int(cfg.get("macd_slow", 26))
        macd_sig_p = int(cfg.get("macd_signal", 9))
        bb_p = int(cfg.get("bb_period", 20))
        bb_std_mult = float(cfg.get("bb_std", 2.0))
        adx_p = int(cfg.get("adx_period", 14))
        strict_suff = bool(cfg.get("strict_indicator_sufficiency", True))

        n_bars = len(bars)
        if n_bars == 0:
            return {
                "symbol": symbol,
                "bars_count": 0,
                "status": "NO_DATA",
                "series": [],
                "latest": None,
            }

        closes: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        opens: List[float] = []
        vols: List[int] = []

        for b in bars:
            c = float(b["close"])
            h = float(b["high"]) if (b.get("high") is not None and float(b["high"]) > 0) else c
            l = float(b["low"]) if (b.get("low") is not None and float(b["low"]) > 0) else c
            o = float(b["open"]) if (b.get("open") is not None and float(b["open"]) > 0) else c
            v = int(b.get("volume") or 0)
            closes.append(c)
            highs.append(h)
            lows.append(l)
            opens.append(o)
            vols.append(v)

        # 1. Wilder's RSI(14)
        rsi_series: List[Optional[float]] = [None] * n_bars
        if n_bars > rsi_p:
            gains = []
            losses = []
            for i in range(1, n_bars):
                delta = closes[i] - closes[i - 1]
                gains.append(max(delta, 0.0))
                losses.append(max(-delta, 0.0))
            avg_g = sum(gains[:rsi_p]) / float(rsi_p)
            avg_l = sum(losses[:rsi_p]) / float(rsi_p)
            if avg_l == 0:
                rsi_series[rsi_p] = 100.0 if avg_g > 0 else 50.0
            else:
                rsi_series[rsi_p] = 100.0 - (100.0 / (1.0 + (avg_g / avg_l)))
            for i in range(rsi_p, len(gains)):
                avg_g = (avg_g * (rsi_p - 1) + gains[i]) / float(rsi_p)
                avg_l = (avg_l * (rsi_p - 1) + losses[i]) / float(rsi_p)
                if avg_l == 0:
                    rsi_series[i + 1] = 100.0 if avg_g > 0 else 50.0
                else:
                    rsi_series[i + 1] = 100.0 - (100.0 / (1.0 + (avg_g / avg_l)))

        # 2. EMA helper
        def calc_ema_list(vals: List[float], period: int) -> List[float]:
            k = 2.0 / (period + 1.0)
            out = [vals[0]]
            for x in vals[1:]:
                out.append(x * k + out[-1] * (1.0 - k))
            return out

        ema9_raw = calc_ema_list(closes, 9)
        ema21_raw = calc_ema_list(closes, 21)
        ema50_raw = calc_ema_list(closes, 50)
        ema200_raw = calc_ema_list(closes, 200)

        ema12_raw = calc_ema_list(closes, macd_fast)
        ema26_raw = calc_ema_list(closes, macd_slow)
        macd_line = [a - b for a, b in zip(ema12_raw, ema26_raw)]
        macd_sig = calc_ema_list(macd_line, macd_sig_p)
        macd_hist = [m - s for m, s in zip(macd_line, macd_sig)]

        # 3. Bollinger Bands (20, 2, population std ddof=0 matching legacy workbook)
        bb_mid: List[Optional[float]] = [None] * n_bars
        bb_up: List[Optional[float]] = [None] * n_bars
        bb_low: List[Optional[float]] = [None] * n_bars
        pct_b: List[Optional[float]] = [None] * n_bars
        bb_width: List[Optional[float]] = [None] * n_bars

        for i in range(bb_p - 1, n_bars):
            w = closes[i - bb_p + 1 : i + 1]
            m = sum(w) / float(bb_p)
            std = math.sqrt(sum((x - m) ** 2 for x in w) / float(bb_p))
            up = m + bb_std_mult * std
            lo = m - bb_std_mult * std
            bb_mid[i] = m
            bb_up[i] = up
            bb_low[i] = lo
            if up != lo:
                pct_b[i] = (closes[i] - lo) / (up - lo)
            bb_width[i] = ((up - lo) / m) if m > 0 else None

        # 4. Daily Typical-Price Proxy ((H+L+C)/3) & 20-Day Rolling Volume-Weighted Typical Price
        tp_daily: List[float] = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n_bars)]
        vwap_rolling20: List[Optional[float]] = [None] * n_bars
        for i in range(n_bars):
            start_w = max(0, i - 19)
            vol_sum = sum(vols[start_w : i + 1])
            if vol_sum > 0:
                pv_sum = sum(tp_daily[j] * vols[j] for j in range(start_w, i + 1))
                vwap_rolling20[i] = pv_sum / float(vol_sum)
            else:
                vwap_rolling20[i] = tp_daily[i]

        # 5. ADX(14) with +DI and -DI
        adx_series: List[Optional[float]] = [None] * n_bars
        pdi_series: List[Optional[float]] = [0.0] * n_bars
        mdi_series: List[Optional[float]] = [0.0] * n_bars
        if n_bars >= 2:
            trs, pdms, mdms = [], [], []
            for i in range(1, n_bars):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
                up = highs[i] - highs[i - 1]
                dn = lows[i - 1] - lows[i]
                pdm = up if (up > dn and up > 0) else 0.0
                mdm = dn if (dn > up and dn > 0) else 0.0
                trs.append(tr)
                pdms.append(pdm)
                mdms.append(mdm)

            if len(trs) >= adx_p:
                atr = sum(trs[:adx_p])
                apdm = sum(pdms[:adx_p])
                amdm = sum(mdms[:adx_p])
                dxs: List[Tuple[int, float]] = []
                for idx_tr in range(adx_p - 1, len(trs)):
                    bar_idx = idx_tr + 1
                    if idx_tr >= adx_p:
                        atr = atr - (atr / adx_p) + trs[idx_tr]
                        apdm = apdm - (apdm / adx_p) + pdms[idx_tr]
                        amdm = amdm - (amdm / adx_p) + mdms[idx_tr]
                    pdi = (100.0 * apdm / atr) if atr > 0 else 0.0
                    mdi = (100.0 * amdm / atr) if atr > 0 else 0.0
                    dx = (100.0 * abs(pdi - mdi) / (pdi + mdi)) if (pdi + mdi) > 0 else 0.0
                    pdi_series[bar_idx] = pdi
                    mdi_series[bar_idx] = mdi
                    dxs.append((bar_idx, dx))

                if dxs:
                    adx_val = dxs[0][1]
                    adx_series[dxs[0][0]] = adx_val
                    for bar_idx, dx_val in dxs[1:]:
                        adx_val = (adx_val * (adx_p - 1) + dx_val) / float(adx_p)
                        adx_series[bar_idx] = adx_val

        # Build per-bar series (strictly causal — bar i only uses indices 0..i)
        buy_th = int(cfg.get("signal_buy_threshold", 3))
        sell_th = int(cfg.get("signal_sell_threshold", -2))

        series_out: List[Dict[str, Any]] = []
        for i in range(n_bars):
            obs_count = i + 1
            c_val = closes[i]
            h_val = highs[i]
            l_val = lows[i]
            o_val = opens[i]
            v_val = vols[i]
            tp_val = tp_daily[i]

            r_val = rsi_series[i]
            m_val = macd_line[i] if obs_count >= macd_slow or not strict_suff else None
            ms_val = macd_sig[i] if obs_count >= macd_slow or not strict_suff else None
            mh_val = macd_hist[i] if obs_count >= macd_slow or not strict_suff else None

            e9 = ema9_raw[i] if obs_count >= 9 or not strict_suff else None
            e21 = ema21_raw[i] if obs_count >= 21 or not strict_suff else None
            e50 = ema50_raw[i] if obs_count >= 50 or not strict_suff else None
            e200_strict = ema200_raw[i] if obs_count >= 200 else None
            e200_rec = ema200_raw[i]
            e200_display = e200_strict if strict_suff else e200_rec

            adx_v = adx_series[i]
            pdi_v = pdi_series[i]
            mdi_v = mdi_series[i]

            # Score each of the 9 indicators (matching legacy 9-factor composite & transparent rules)
            score = 0
            # 1. MACD
            if mh_val is not None:
                score += 1 if mh_val > 0 else (-1 if mh_val < 0 else 0)
            # 2. RSI
            if r_val is not None:
                if r_val < 30:
                    score += 1
                elif r_val > 70:
                    score -= 1
            # 3. Bollinger %B
            if pct_b[i] is not None:
                if pct_b[i] > 0.55:
                    score += 1
                elif pct_b[i] < 0.45:
                    score -= 1
            # 4. EMA 9
            if ema9_raw[i] is not None:
                score += 1 if c_val > ema9_raw[i] else -1
            # 5. EMA 21
            if ema21_raw[i] is not None:
                score += 1 if c_val > ema21_raw[i] else -1
            # 6. EMA 50
            if ema50_raw[i] is not None:
                score += 1 if c_val > ema50_raw[i] else -1
            # 7. EMA 200 (uses recursive in legacy score; in strict mode only when sufficient or noted)
            if (e200_display is not None):
                score += 1 if c_val > e200_display else -1
            elif not strict_suff or obs_count >= 50:
                score += 1 if c_val > e200_rec else -1
            # 8. Typical Price / Pivot
            score += 1 if c_val >= tp_val else -1
            # 9. ADX +DI/-DI
            if adx_v is not None and adx_v >= 20:
                score += 1 if pdi_v > mdi_v else -1

            if obs_count < 15:
                action = "INSUFFICIENT DATA"
            elif score >= buy_th:
                action = "BUY"
            elif score <= sell_th:
                action = "SELL"
            else:
                action = "HOLD"

            series_out.append({
                "trade_date": bars[i]["trade_date"],
                "open": o_val,
                "high": h_val,
                "low": l_val,
                "close": c_val,
                "pr_close": bars[i].get("pr_close"),
                "volume": v_val,
                "rsi14": r_val,
                "macd": m_val,
                "macd_sig": ms_val,
                "macd_hist": mh_val,
                "bb_up": bb_up[i],
                "bb_mid": bb_mid[i],
                "bb_low": bb_low[i],
                "pct_b": pct_b[i],
                "bb_width": bb_width[i],
                "ema9": e9,
                "ema21": e21,
                "ema50": e50,
                "ema200": e200_display,
                "ema200_recursive": e200_rec,
                "ema200_sufficient": obs_count >= 200,
                "vwap_typical_daily": tp_val,
                "vwap_rolling20": vwap_rolling20[i],
                "adx14": adx_v,
                "plus_di": pdi_v,
                "minus_di": mdi_v,
                "score": score,
                "action": action,
            })

        last_bar = series_out[-1]
        prev_bar = series_out[-2] if n_bars >= 2 else None
        pr_cl_ref = float(bars[-1]["pr_close"]) if (bars[-1].get("pr_close") and float(bars[-1]["pr_close"]) > 0) else (prev_bar["close"] if prev_bar else last_bar["close"])
        chg = last_bar["close"] - pr_cl_ref
        chg_pct = (chg / pr_cl_ref * 100.0) if pr_cl_ref > 0 else 0.0

        daily_pivots = self.compute_classic_fib_camarilla_pivots(last_bar["high"], last_bar["low"], last_bar["close"])
        weekly_pivots = self.compute_weekly_pivots(bars)

        signal_detail = self._build_explainable_signal(
            symbol=symbol,
            n_bars=n_bars,
            last_bar=last_bar,
            prev_bar=prev_bar,
            daily_pivots=daily_pivots["classic"],
            weekly_pivots=weekly_pivots.get("pivots"),
            strict_suff=strict_suff,
            is_futures_eligible=is_futures_eligible,
            cfg=cfg,
        )

        # RSI YTD high/low
        valid_rsis = [(s["rsi14"], s["trade_date"]) for s in series_out if s["rsi14"] is not None]
        rsi_high = max(valid_rsis, key=lambda x: x[0]) if valid_rsis else (None, None)
        rsi_low = min(valid_rsis, key=lambda x: x[0]) if valid_rsis else (None, None)

        vol_20d_avg = sum(vols[-20:]) / float(min(20, n_bars))
        sma50_val = (sum(closes[-50:]) / 50.0) if n_bars >= 50 else None

        warnings: List[str] = []
        if n_bars < 200:
            warnings.append(
                f"EMA 200 requires 200 sessions for full lookback; dataset contains {n_bars} sessions (01-Jan-2026 to {last_bar['trade_date']}). "
                f"Strict mode shows N/A (recursive warm-up value: {last_bar['ema200_recursive']:.2f} PKR)."
            )
        if n_bars < 26:
            warnings.append(f"Insufficient history ({n_bars} bars < 26 bars) for reliable MACD/Bollinger/ADX initialization.")
        warnings.append(
            "VWAP Note: True intraday VWAP requires tick/intraday bars. Because source data is daily OHLCV, "
            "both single-day Typical Price ((H+L+C)/3) and 20-Day Rolling Volume-Weighted Typical Price are shown and explicitly labeled as daily approximations."
        )

        latest_summary = {
            "symbol": symbol,
            "display_label": "MLCF (MLF)" if symbol == "MLCF" else symbol,
            "is_core_36": symbol in CORE_36_TICKERS,
            "is_futures_eligible": is_futures_eligible,
            "bars_count": n_bars,
            "first_date": bars[0]["trade_date"],
            "latest_date": last_bar["trade_date"],
            "open": last_bar["open"],
            "high": last_bar["high"],
            "low": last_bar["low"],
            "close": last_bar["close"],
            "pr_close": pr_cl_ref,
            "change": chg,
            "change_val": chg,
            "change_pct": chg_pct,
            "volume": last_bar["volume"],
            "volume_20d_avg": vol_20d_avg,
            "rsi14": last_bar["rsi14"],
            "prev_rsi14": prev_bar["rsi14"] if prev_bar else None,
            "rsi_zone": (
                "NO DATA" if last_bar["rsi14"] is None
                else ("OVERBOUGHT" if last_bar["rsi14"] >= 70.0 else ("OVERSOLD" if last_bar["rsi14"] <= 30.0 else "NEUTRAL"))
            ),
            "rsi_ytd_high": {"value": rsi_high[0], "date": rsi_high[1]},
            "rsi_ytd_low": {"value": rsi_low[0], "date": rsi_low[1]},
            "sma20": last_bar["bb_mid"],
            "sma50": sma50_val,
            "trend_vs_sma20": (
                "N/A" if last_bar["bb_mid"] is None
                else ("ABOVE" if last_bar["close"] >= last_bar["bb_mid"] else "BELOW")
            ),
            "macd": last_bar["macd"],
            "macd_sig": last_bar["macd_sig"],
            "macd_hist": last_bar["macd_hist"],
            "bb_up": last_bar["bb_up"],
            "bb_mid": last_bar["bb_mid"],
            "bb_low": last_bar["bb_low"],
            "pct_b": last_bar["pct_b"],
            "bb_width": last_bar["bb_width"],
            "ema9": last_bar["ema9"],
            "ema21": last_bar["ema21"],
            "ema50": last_bar["ema50"],
            "ema200": last_bar["ema200"],
            "ema200_recursive": last_bar["ema200_recursive"],
            "ema200_sufficient": last_bar["ema200_sufficient"],
            "vwap_typical_daily": last_bar["vwap_typical_daily"],
            "vwap_rolling20": last_bar["vwap_rolling20"],
            "adx14": last_bar["adx14"],
            "plus_di": last_bar["plus_di"],
            "minus_di": last_bar["minus_di"],
            "daily_pivots": daily_pivots,
            "weekly_pivots": weekly_pivots,
            "signal": signal_detail,
            "warnings": warnings,
            "data_quality_status": "OK" if n_bars >= 50 else ("PARTIAL_HISTORY" if n_bars >= 15 else "INSUFFICIENT_HISTORY"),
        }

        return {
            "symbol": symbol,
            "bars_count": n_bars,
            "status": "OK",
            "latest": latest_summary,
            "series": series_out,
        }

    def _build_explainable_signal(
        self,
        symbol: str,
        n_bars: int,
        last_bar: Dict[str, Any],
        prev_bar: Optional[Dict[str, Any]],
        daily_pivots: Dict[str, float],
        weekly_pivots: Optional[Dict[str, float]],
        strict_suff: bool,
        is_futures_eligible: bool,
        cfg: Dict[str, Any],
    ) -> Dict[str, Any]:
        c = last_bar["close"]
        p = daily_pivots["P"]
        r1 = daily_pivots["R1"]
        r2 = daily_pivots["R2"]
        s1 = daily_pivots["S1"]
        s2 = daily_pivots["S2"]

        if n_bars < 26 or last_bar["rsi14"] is None:
            return {
                "action": "INSUFFICIENT DATA",
                "combined_signal": "INSUFFICIENT DATA",
                "legacy_action": "WAIT",
                "score": 0,
                "max_score": 9,
                "confidence": "N/A (Insufficient History)",
                "holding_horizon": "N/A",
                "reference_price": c,
                "reference_date": last_bar["trade_date"],
                "entry_reference": "N/A",
                "stop_loss_reference": "N/A",
                "target_reference": "N/A",
                "short_sell_reference": "N/A",
                "risk_reward": "N/A",
                "invalidation": "Insufficient historical observations (< 26 trading sessions).",
                "invalidation_condition": "Insufficient historical observations (< 26 trading sessions).",
                "rationale": [
                    f"Only {n_bars} sessions of historical OHLCV exist for {symbol}; minimum 26 sessions required for reliable multi-indicator confirmation."
                ],
                "indicator_breakdown": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        breakdown = []
        rationale = []

        # 1. MACD
        mh = last_bar["macd_hist"]
        m_val = last_bar["macd"]
        ms_val = last_bar["macd_sig"]
        macd_bull = mh is not None and mh > 0
        breakdown.append({
            "indicator": "MACD (12,26,9)",
            "value": f"{m_val:.2f} / sig {ms_val:.2f} (hist {mh:+.2f})",
            "signal": "BULLISH MOMENTUM" if macd_bull else "BEAR CROSS / NEG HIST",
            "advice": "BUY" if macd_bull else "SELL",
            "vote": 1 if macd_bull else -1,
        })

        # 2. RSI(14)
        rsi = last_bar["rsi14"]
        if rsi <= 30:
            rsi_sig, rsi_adv, rsi_vote = "OVERSOLD (<30)", "BUY REBOUND", 1
        elif rsi >= 70:
            rsi_sig, rsi_adv, rsi_vote = "OVERBOUGHT (>70)", "TAKE PROFIT / SELL", -1
        else:
            rsi_sig, rsi_adv, rsi_vote = "NEUTRAL (30-70)", "HOLD", 0
        breakdown.append({
            "indicator": "RSI (14 Wilder)",
            "value": f"{rsi:.2f}",
            "signal": rsi_sig,
            "advice": rsi_adv,
            "vote": rsi_vote,
        })

        # 3. Bollinger(20,2)
        pb = last_bar["pct_b"]
        bw = last_bar["bb_width"]
        bb_vote = 1 if (pb is not None and pb >= 0.55) else (-1 if (pb is not None and pb <= 0.45) else 0)
        breakdown.append({
            "indicator": "Bollinger (20,2)",
            "value": f"%B {pb:.2f} | BW {bw:.2f}" if (pb is not None and bw is not None) else "N/A",
            "signal": "UPPER HALF MOMENTUM" if bb_vote > 0 else ("LOWER HALF WEAKNESS" if bb_vote < 0 else "MID BAND"),
            "advice": "HOLD / TREND" if bb_vote >= 0 else "CAUTION",
            "vote": bb_vote,
        })

        # 4. EMA 9
        e9 = last_bar["ema9"]
        e9_vote = 1 if c > e9 else -1
        breakdown.append({
            "indicator": "EMA 9",
            "value": f"{e9:.2f}",
            "signal": "UP (Close > EMA9)" if e9_vote > 0 else "DOWN (Close < EMA9)",
            "advice": "RIDE LONG" if e9_vote > 0 else "SHORT-TERM WEAK",
            "vote": e9_vote,
        })

        # 5. EMA 21
        e21 = last_bar["ema21"]
        e21_vote = 1 if c > e21 else -1
        breakdown.append({
            "indicator": "EMA 21",
            "value": f"{e21:.2f}",
            "signal": "ABOVE = Entry Valid" if e21_vote > 0 else "BELOW = Pullback",
            "advice": "ADD LONGS" if e21_vote > 0 else "AVOID LONGS",
            "vote": e21_vote,
        })

        # 6. EMA 50
        e50 = last_bar["ema50"] if n_bars >= 50 else None
        e50_vote = (1 if c > e50 else -1) if e50 is not None else 0
        breakdown.append({
            "indicator": "EMA 50",
            "value": f"{e50:.2f}" if e50 is not None else f"N/A ({n_bars}/50 bars)",
            "signal": "Stop-Loss Anchor Held" if e50_vote > 0 else ("Below Medium Trend" if e50_vote < 0 else "Insufficient Bars"),
            "advice": "TRAIL STOP HERE" if e50_vote > 0 else "DEFENSIVE",
            "vote": e50_vote,
        })

        # 7. EMA 200
        e200_rec = last_bar["ema200_recursive"]
        if strict_suff and n_bars < 200:
            e200_val_str = f"N/A ({n_bars}/200 bars; warm-up {e200_rec:.2f})"
            e200_sig = "INSUFFICIENT HISTORY (<200 BARS)"
            e200_adv = "N/A (STRICT)"
            e200_vote = 1 if c > e200_rec else -1  # Keep legacy score parity while flagging sufficiency
        else:
            e200_val_str = f"{e200_rec:.2f}"
            e200_vote = 1 if c > e200_rec else -1
            e200_sig = "LONG-TERM UP" if e200_vote > 0 else "LONG-TERM DOWN"
            e200_adv = "LONG BIAS" if e200_vote > 0 else "BEAR BIAS"
        breakdown.append({
            "indicator": "EMA 200",
            "value": e200_val_str,
            "signal": e200_sig,
            "advice": e200_adv,
            "vote": e200_vote,
        })

        # 8. Daily Typical-Price / Pivot Proxy
        tp = last_bar["vwap_typical_daily"]
        rw = last_bar["vwap_rolling20"]
        tp_vote = 1 if c >= tp else -1
        breakdown.append({
            "indicator": "Daily TP / 20D VWAP Proxy",
            "value": f"TP {tp:.2f} | 20D VWAP {rw:.2f}",
            "signal": "ABOVE Daily Typical Price" if tp_vote > 0 else "BELOW Daily Typical Price",
            "advice": "BUY BREAKOUT" if tp_vote > 0 else "SELL RALLIES",
            "vote": tp_vote,
        })

        # 9. ADX(14)
        adx = last_bar["adx14"]
        pdi = last_bar["plus_di"]
        mdi = last_bar["minus_di"]
        if adx is not None and adx >= 20:
            adx_vote = 1 if pdi > mdi else -1
            adx_sig = "STRONG UP TREND" if adx_vote > 0 else "STRONG DOWN TREND"
            adx_adv = "TREND TRADE"
        else:
            adx_vote = 0
            adx_sig = "WEAK / RANGE (<20)"
            adx_adv = "RANGE / MEAN REVERT"
        breakdown.append({
            "indicator": "ADX (14)",
            "value": f"{adx:.1f} (+DI {pdi:.0f} / -DI {mdi:.0f})" if adx is not None else "N/A",
            "signal": adx_sig,
            "advice": adx_adv,
            "vote": adx_vote,
        })

        score = last_bar["score"]
        buy_th = int(cfg.get("signal_buy_threshold", 3))
        sell_th = int(cfg.get("signal_sell_threshold", -2))
        short_th = int(cfg.get("signal_short_threshold", -5))

        if score >= buy_th and c >= e21:
            combined_signal = "Buy"
        elif score <= short_th and is_futures_eligible and (adx or 0) >= 20 and mdi > pdi:
            combined_signal = "Short Sell"
        elif score <= sell_th:
            combined_signal = "Sell"
        else:
            combined_signal = "Hold / Neutral"

        # Reference levels (analytical only)
        if combined_signal == "Buy":
            entry_ref = round(p if c >= p else r1, 2)
            stop_ref = round(min(s1, e21), 2)
            target_ref = round(r2 if c >= r1 else r1, 2)
            invalidation = f"Daily close below S1 ({s1:.2f} PKR) or EMA 21 ({e21:.2f} PKR)."
        elif combined_signal in ("Sell", "Short Sell"):
            entry_ref = round(p if c <= p else s1, 2)
            stop_ref = round(max(r1, e21), 2)
            target_ref = round(s2 if c <= s1 else s1, 2)
            invalidation = f"Daily close above R1 ({r1:.2f} PKR) or EMA 21 ({e21:.2f} PKR)."
        else:
            entry_ref = round(r1, 2)
            stop_ref = round(s1, 2)
            target_ref = round(r2, 2)
            invalidation = f"Range-bound between S1 ({s1:.2f} PKR) and R1 ({r1:.2f} PKR); wait for directional breakout."

        risk = abs(c - stop_ref)
        reward = abs(target_ref - c)
        rr_ratio = round(reward / risk, 2) if risk > 0.0001 else "N/A"

        short_trigger_note = (
            f"Analytical Short-Sell Trigger < {min(s1, e21):.2f} PKR (stop {r1:.2f} PKR) — "
            + ("Eligible on PSX Deliverables Futures Market." if is_futures_eligible else "NOT eligible for Deliverable Futures short-selling; regular market only.")
        )

        sma20 = last_bar["bb_mid"] or c
        sma50 = last_bar["ema50"] or c
        rationale.append(
            f"Trend: Close {c:.2f} PKR is {((c - sma20)/sma20*100):+.2f}% vs SMA(20) ({sma20:.2f}) and EMA(21) ({e21:.2f})."
        )
        rationale.append(
            f"Momentum: Wilder RSI(14) = {rsi:.2f} ({'OVERSOLD' if rsi<=30 else ('OVERBOUGHT' if rsi>=70 else 'NEUTRAL')}) | MACD Hist = {mh:+.2f}."
        )
        rationale.append(
            f"Pivot Context: Close ({c:.2f}) is {'ABOVE' if c >= p else 'BELOW'} Daily Classic Pivot P ({p:.2f}); R1 = {r1:.2f}, S1 = {s1:.2f}."
        )
        if weekly_pivots:
            rationale.append(
                f"Weekly Structure: Previous Completed Week Pivot P = {weekly_pivots['P']:.2f} (W-R1 {weekly_pivots['R1']:.2f} / W-S1 {weekly_pivots['S1']:.2f})."
            )
        rationale.append(
            f"Composite Score: {score:+d}/9 -> {combined_signal.upper()}. Analytical reference levels are not guaranteed execution prices."
        )

        confidence = "HIGH" if abs(score) >= 5 else ("MODERATE" if abs(score) >= 3 else "LOW")
        return {
            "action": combined_signal.upper(),
            "combined_signal": combined_signal.upper(),
            "legacy_action": last_bar["action"],
            "score": score,
            "max_score": 9,
            "confidence": confidence,
            "holding_horizon": "Swing (3-10 Sessions)",
            "reference_price": c,
            "reference_date": last_bar["trade_date"],
            "entry_reference": entry_ref,
            "stop_loss_reference": stop_ref,
            "target_reference": target_ref,
            "short_sell_reference": short_trigger_note,
            "risk_reward": rr_ratio,
            "invalidation": invalidation,
            "invalidation_condition": invalidation,
            "rationale": rationale,
            "indicator_breakdown": breakdown,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_ticker_analysis(self, symbol: str, tail_bars: int = 200) -> Dict[str, Any]:
        sym = self.resolve_ticker(symbol)
        with get_connection(self.db_path) as c:
            bars = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT trade_date, open, high, low, close, pr_close, avg_price, volume
                    FROM equity_ohlcv
                    WHERE symbol = ?
                    ORDER BY trade_date ASC
                    """,
                    (sym,),
                ).fetchall()
            ]
            fut_cnt = c.execute(
                "SELECT COUNT(*) FROM futures_ohlcv WHERE base_symbol = ?",
                (sym,),
            ).fetchone()[0]

        res = self.calculate_series_for_bars(sym, bars, is_futures_eligible=(fut_cnt > 0))
        res["display_label"] = "MLCF (MLF)" if sym == "MLCF" else sym
        if res["series"] and tail_bars > 0:
            res["series"] = res["series"][-tail_bars:]
        return res

    def get_universe_summary(
        self,
        scope: str = "core36",
        search: Optional[str] = None,
        signal_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return searchable summary table for either the 36 core tickers (scope='core36')
        or all 531 PSX tickers (scope='all'). Uses indicator_cache for instant response.
        """
        cfg = self.repo.get_settings()
        rule_ver = int(cfg.get("rule_version", 1))
        now = datetime.now(timezone.utc).isoformat()

        with get_connection(self.db_path) as c:
            from psx_app.database.turso import enabled
            cache_revision = c.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0] if enabled() else None
            if scope == "core36":
                target_syms = list(CORE_36_TICKERS)
            else:
                target_syms = [
                    r[0]
                    for r in c.execute("SELECT DISTINCT symbol FROM equity_ohlcv ORDER BY symbol ASC").fetchall()
                ]

            if search and search.strip():
                q = self.resolve_ticker(search.strip())
                target_syms = [s for s in target_syms if q in s or s in search.strip().upper()]

            fut_bases = {
                r[0]
                for r in c.execute("SELECT DISTINCT base_symbol FROM futures_ohlcv").fetchall()
            }

            cached_rows = {
                r["symbol"]: json.loads(r["payload_json"])
                for r in c.execute(
                    "SELECT symbol, payload_json FROM indicator_cache WHERE rule_version = ?",
                    (rule_ver,),
                ).fetchall()
            }

            summaries: List[Dict[str, Any]] = []
            new_cache_entries = []

            for sym in target_syms:
                if sym in cached_rows:
                    item = cached_rows[sym]
                else:
                    bars = [
                        dict(r)
                        for r in c.execute(
                            """
                            SELECT trade_date, open, high, low, close, pr_close, avg_price, volume
                            FROM equity_ohlcv
                            WHERE symbol = ?
                            ORDER BY trade_date ASC
                            """,
                            (sym,),
                        ).fetchall()
                    ]
                    calc = self.calculate_series_for_bars(sym, bars, settings=cfg, is_futures_eligible=(sym in fut_bases))
                    item = calc["latest"]
                    if item:
                        new_cache_entries.append((sym, item["latest_date"], rule_ver, json.dumps(item), now))
                if item:
                    if signal_filter and signal_filter != "ALL":
                        if item["signal"]["combined_signal"].upper() != signal_filter.upper() and item["signal"]["legacy_action"].upper() != signal_filter.upper():
                            continue
                    summaries.append(item)

            if new_cache_entries and enabled():
                c.execute('BEGIN IMMEDIATE')
                if c.execute("SELECT value FROM psx_runtime WHERE key='revision'").fetchone()[0] != cache_revision:
                    new_cache_entries = []
                if not new_cache_entries:
                    c.rollback()
            if new_cache_entries:
                c.executemany(
                    """
                    INSERT OR REPLACE INTO indicator_cache (symbol, trade_date, rule_version, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    new_cache_entries,
                )
                c.commit()

        signal_counts: Dict[str, int] = {}
        for it in summaries:
            act = it["signal"]["combined_signal"].upper()
            signal_counts[act] = signal_counts.get(act, 0) + 1
            if "display_label" not in it:
                it["display_label"] = "MLCF (MLF)" if it["symbol"] == "MLCF" else it["symbol"]

        return {
            "scope": scope,
            "count": len(summaries),
            "signal_counts": signal_counts,
            "core_36_tickers": CORE_36_TICKERS,
            "items": summaries,
        }
