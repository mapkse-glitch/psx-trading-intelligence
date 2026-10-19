# Architectural Assumptions, Legacy Discrepancies & Engineering Decisions

This document records every ambiguity, contradiction, or edge case discovered between the legacy specifications and the actual Google Drive files, along with how the **Unified PSX Trading Intelligence Dashboard** resolves and exposes them through configuration.

---

## 1. Resolved Discrepancies Between Legacy Prompts and Actual Files

### ADR-01: Ticker `MLF` (Prompt Text) vs `MLCF` (Actual PSX Symbol & Workbook Sheet)
- **Observation**: Section 9 of the Master Prompt lists 36 tickers including `MLF`. Inspection of `PSX_RSI_Pivot_Analysis (4).xlsx`, `PSX_Top5_Volume_Rate_12-08-2026_to_16-10-2026 (1).xlsx`, `Input folder/MLCF.txt`, and `2026_YEAR.xlsx` confirms that the actual PSX symbol and worksheet name is **`MLCF`** (Maple Leaf Cement Factory Ltd.), and no symbol `MLF` exists on PSX.
- **Decision**: Use `MLCF` as the canonical 36-ticker symbol so all 36 existing worksheets (`ATRL`, `DGKC`, `GAL`, `GHNI`, `LUCK`, `MLCF`, `NBP`, `NRL`, `NML`, `NPL`, `NCPL`, `OGDC`, `PSO`, `PPL`, `PRL`, `SEARL`, `THCCL`, `TRG`, `BOP`, `CPHL`, `PTC`, `SNGP`, `SSGC`, `NETSOL`, `FFC`, `UBL`, `HBL`, `SYS`, `MUGHAL`, `ISL`, `INIL`, `HUBC`, `PSX`, `SAZEW`, `ENGROH`, `PAEL`) are preserved without omission. In addition, the search/parser aliases `MLF → MLCF` automatically so user queries for `MLF` resolve seamlessly.

### ADR-02: Top 5 Price Summary TXT Column Order vs Export Table Column Order
- **Observation**: In the raw `Input folder/{TICKER}.txt` files (e.g., `ATRL.txt`), the 4 CSV columns are ordered:
  `Col 0 = Rate`, `Col 1 = Trades`, `Col 2 = Volume`, `Col 3 = Traded Value`.
  However, in the exported register `PSX_Top5_Volume_Rate_12-08-2026_to_16-10-2026 (1).xlsx`, the 4 visible columns are ordered:
  `Col A = Rank`, `Col B = Rate`, `Col C = Volume`, `Col D = Trades`.
- **Decision**: The TXT parser explicitly maps `Col 0 → Rate`, `Col 1 → Trades`, `Col 2 → Volume` (validated via `Rate × Volume ≈ Traded Value`), ranks by `Volume DESC`, and outputs `Rank, Rate, Volume, Trades` in the UI and Excel export.

### ADR-03: Module B Historical Execution Granularity (`Daily Trade Summary` vs Raw `TradeLog`)
- **Observation**: The Google Drive `Input folder` contains only one raw TradeLog file: `TradeLog-16-10-2026_ALL.txt` (30 executions on `2026-10-16`, all for Account `91404`). Meanwhile, `Output folder/Trade_Summary_Account_91404_Updated_2026-10-16.xlsx` contains 36 trading days (`2026-08-17` to `2026-10-16`) and `Trade_Summary_Account_91269_Updated_2026-10-15.xlsx` contains 20 trading days (`2026-08-24` to `2026-10-15`) stored as symbol-date blocks in the `Daily Trade Summary` worksheet (the legacy workbooks did not retain a `Trade Log` worksheet for prior dates).
- **Decision**:
  1. During historical migration, import all symbol-date blocks from `Daily Trade Summary` (`2026-08-17` to `2026-10-15` for Account `91404`, and `2026-08-24` to `2026-10-15` for Account `91269`) with provenance `origin_type = 'LEGACY_MIGRATED'`.
  2. For `2026-10-16` (Account `91404`), import the 30 raw executions from `TradeLog-16-10-2026_ALL.txt` (`origin_type = 'RAW_EXECUTIONS'`), calculate the symbol-date summaries deterministically from the 30 raw executions, and reconcile them against the `16 Oct 2026` block in `Trade_Summary_Account_91404_Updated_2026-10-16.xlsx` (which matches to **0.00 PKR difference** across all 5 symbols!).
  3. Deduplicate `2026-10-16` so that the legacy `16 Oct 2026` summary block and `TradeLog-16-10-2026_ALL.txt` are **never double-counted**.
  4. When exporting `Trade_Summary_Account_91404.xlsx` and `Trade_Summary_Account_91269.xlsx`, include all 10 legacy sheets (`Dashboard`, `Daily Summary`, `MTD Summary`, `QTD Summary`, `YTD Summary`, `Monthly Summary`, `Yearly Summary`, `Symbol Performance`, `Daily Trade Summary`, `Settings`) **plus** `Trade Log` and `Data Checks` (configurable via export preset: `Standard 12-Sheet` or `Strict Legacy 10-Sheet`).

### ADR-04: Module C Source Files (`2026.xlsx` / `2026_YEAR.xlsx` / `2026F.xlsx` vs `.csv`)
- **Observation**: The Module C prompt refers to `2026F.csv` and `2026_compare.csv`, while the Google Drive `Input folder` provides `2026F.xlsx`, `2026.xlsx`, and `2026_YEAR.xlsx` (where `2026.xlsx` and `2026_YEAR.xlsx` are 100% identical across all 95,773 rows of cols 1–9).
- **Decision**: The ingestion engine accepts both `.csv` and `.xlsx` formats for Cash/Spot (`2026.xlsx`, `2026_YEAR.xlsx`, `2026_compare.csv`) and Futures (`2026F.xlsx`, `2026F.csv`). Furthermore, when both `2026.xlsx` and `2026_YEAR.xlsx` are present, the migration engine detects that all 95,773 `(DATE, SYMBOL)` records are identical and deduplicates them automatically with zero double-counting.

### ADR-05: Module C Two-Month Rolling Retention Policy
- **Observation**: `2026F.xlsx` contains 52 trading dates (`2026-08-04` to `2026-10-16`, 6,204 rows), whereas `Output folder/Futures_Analysis (3).xlsx` retains 34 trading dates (`2026-09-01` to `2026-10-16`, 3,913 rows) in its hidden `Data` sheet because August 2026 was pruned under the 2-month rolling window (September + October 2026).
- **Decision**: Store all 6,204 futures rows (`2026-08-04` to `2026-10-16`) permanently in the SQLite `futures_ohlcv` table. Apply the configurable **2-Month Rolling Window** (`futures_rolling_months = 2`, toggleable in UI & Settings) to the active comparison views and the `Futures_Analysis.xlsx` export, and provide a non-destructive **Retention Preview** modal showing exactly which older calendar months are outside the active window.

### ADR-06: Module D EMA 200 Data Sufficiency vs Legacy Recursive Initialization
- **Observation**: `2026_YEAR.xlsx` has at most **196 trading sessions** (`2026-01-01` to `2026-10-16`). Strictly speaking, `EMA 200` requires 200 observations (`N >= 200`). However, the legacy workbook `PSX_RSI_Pivot_Analysis (4).xlsx` initialized `EMA 200` on bar 1 (`EMA_0 = Close_0`) and recursively updated `EMA_t = α·Close_t + (1-α)·EMA_{t-1}`, producing a numeric value (`951.04` for `ATRL` on `2026-10-16`).
- **Decision**:
  - By default (`strict_indicator_sufficiency = True`), any indicator whose required lookback exceeds available bars (`bars < 200` for `EMA 200`, `bars < 15` for `RSI 14`, `bars < 28` for `ADX 14`, `bars < 26` for `MACD`, `bars < 20` for `Bollinger`) is flagged as **`N/A (Insufficient History: 196/200 bars)`** in the UI and excluded from fabricating false trend signals.
  - For full reconciliation transparency with `PSX_RSI_Pivot_Analysis (4).xlsx`, the system also computes the recursive warm-up value (`ema200_recursive`) and allows toggling `strict_indicator_sufficiency` in **Settings**.

### ADR-07: Module D Daily VWAP Proxy vs True Intraday VWAP
- **Observation**: The legacy workbook `PSX_RSI_Pivot_Analysis (4).xlsx` includes a column labeled `VWAP` in `{TICKER}_DATA` that is actually the single-day **Typical Price** `(High + Low + Close) / 3` (which equals the Classic Pivot Point `P`).
- **Decision**: Because only daily OHLCV data is provided for the 531 tickers, true intraday VWAP cannot be computed. The dashboard explicitly labels the metric as **`Daily Typical-Price Proxy ((H+L+C)/3) & 20D Rolling VWAP Proxy — Not Intraday VWAP`** in the UI and documentation, preventing any confusion with intraday execution VWAP.
