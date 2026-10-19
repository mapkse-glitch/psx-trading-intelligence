# Known Limitations, Historical Data Notes & Design Boundaries

## 1. Historical vs Raw Execution Coverage in Module B (Accounts 91404 & 91269)
- **What is available in the Google Drive input folder**:
  - `Input folder/TradeLog-16-10-2026_ALL.txt` contains raw execution-level trades (`32` executions) for **Account `91404` on `2026-10-16` only**.
  - Raw execution-level `TradeLog` `.txt` files for earlier trading dates (`17-Aug-2026` to `15-Oct-2026`) and for **Account `91269`** (`24-Aug-2026` to `15-Oct-2026`) were not present in `Input folder/`.
- **How the system handles this transparently**:
  - All `36` trading days of Account `91404` (`229` symbol-date summaries) and all `20` trading days of Account `91269` (`66` symbol-date summaries) were migrated from `Daily Trade Summary` in `Trade_Summary_Account_91404_Updated_2026-10-16.xlsx` and `Trade_Summary_Account_91269_Updated_2026-10-15.xlsx` with `origin_type = 'LEGACY_MIGRATED'`.
  - When `TradeLog-16-10-2026_ALL.txt` was imported, the `2026-10-16` rows for Account `91404` were automatically upgraded to `origin_type = 'RAW_EXECUTIONS'` without double-counting.
  - Any future `TradeLog` `.txt`/`.csv`/`.xlsx` files uploaded for either `91404` or `91269` will populate `trade_executions` and compute symbol/daily/MTD/QTD/YTD summaries from raw executions.

---

## 2. EMA-200 Lookback Sufficiency (`196` Trading Sessions in 2026)
- `2026.xlsx` / `2026_YEAR.xlsx` spans `2026-01-01` to `2026-10-16`, which comprises **196 PSX trading sessions** (`4` sessions short of a strict `200`-session lookback).
- The legacy workbook `PSX_RSI_Pivot_Analysis (4).xlsx` initialized `EMA200` recursively from Bar 1 (`Close` of `2026-01-01`), yielding `951.04` for `ATRL` on Bar 196.
- To satisfy both strict quantitative integrity (no fabricated indicator values when lookback `< 200`) and legacy reconciliation:
  - `TechnicalService` sets strict `ema200 = None` (`N/A (196/200 bars)`) when `< 200` sessions exist, while also exposing `ema200_recursive = 951.04` (labeled as warm-up / legacy recursive) so users can reconcile both numbers side by side. Once 4 more daily sessions are imported (`>= 200` bars), strict `ema200` populates automatically.

---

## 3. Daily OHLCV vs True Intraday VWAP
- True Volume-Weighted Average Price (`VWAP`) is an intraday cumulative metric (`sum(TypicalPrice_i * Volume_i) / sum(Volume_i)` across intraday ticks/bars).
- Because the input market files (`2026.xlsx`) contain **daily** OHLCV bars (plus a daily `AVG` column that is `0` on some dates), the legacy `PSX_RSI_Pivot_Analysis (4).xlsx` sheet computed single-bar Typical Price `(High + Low + Close) / 3` under the column header `VWAP`.
- Our application computes both **Daily Typical Price `(H+L+C)/3`** and **20-Day Rolling Volume-Weighted Typical Price**, and explicitly labels both in the UI and exported workbook as daily approximations rather than intraday tick VWAP.

---

## 4. Unmatched Futures Base Symbols (`N/A` Current Value)
- Certain futures contracts in `2026F.xlsx` (or on specific dates) have no corresponding same-date cash equity row in `2026.xlsx` (`28` contract rows on `2026-10-16`).
- Per strict specification rules, the system **never backfills or carries forward** prior-day cash prices; those rows display `Current Value = N/A`, `Difference = N/A`, and `Annualized % = N/A`, and are listed in **08 • Data Quality & Reconciliation**.
