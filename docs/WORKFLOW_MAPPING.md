# Workflow Mapping — Legacy Excel Processes to Unified Application Modules

This document maps each of the four legacy Excel workflows to the unified architecture of the **PSX Trading Intelligence Dashboard**.

---

## 1. End-to-End Unified Architecture Flow

```text
[Manual Upload (.txt/.csv/.xlsx/.zip) OR Google Drive Mirror]
                            │
                            ▼
        [Layer 2: Upload & Staging Orchestrator]
        (SHA-256 Hashing, Archive to data/raw/, Preview)
                            │
        ┌───────────────────┼───────────────────┬───────────────────┐
        ▼                   ▼                   ▼                   ▼
[Module A Parser]   [Module B Parser]   [Module C Parser]   [Module D Parser]
Ticker TXT Files    TradeLog Files      2026F + 2026 Cash   2026_YEAR + INDEX
        │                   │                   │                   │
        └───────────────────┴─────────┬─────────┴───────────────────┘
                                      ▼
                [Canonical SQLite Database (database/app.db)]
          (Atomic Transactions, Deduplication, Revision Auditing)
                                      │
        ┌───────────────────┬─────────┴─────────┬───────────────────┐
        ▼                   ▼                   ▼                   ▼
[Module A Engine]   [Module B Engine]   [Module C Engine]   [Module D Engine]
Top 5 Volume/Rate   Accounts 91404 &    Futures vs Spot     36-Ticker + 531
Rank 1..5           91269 P&L, Slabs,   Same-Date Match,    Universe RSI/MACD/
Chronological       SST, Daily/MTD/     Days Annualized %,  BB/EMA/ADX/Pivots
Register            QTD/YTD/Mo/Yr       2-Mo Retention      & Signal Engine
        │                   │                   │                   │
        └───────────────────┴─────────┬─────────┴───────────────────┘
                                      ▼
      [Unified Web UI (10 Sidebar Views) + Legacy .xlsx Exporters]
```

---

## 2. Detailed Module Mapping

### 2.1 Module A: Daily Top 5 Volume & Rate Register
- **Legacy Process**: Daily upload of 23 `.txt` price-summary files (`ATRL.txt`..`TRG.txt`) to an LLM to append a 5-row Excel table block per sheet in `PSX_Top5_Volume_Rate_*.xlsx`.
- **Unified Dashboard Workflow**:
  - Upload individual `.txt` files or a `.zip` bundle.
  - Parser extracts ticker and date from line 1 (`{TICKER} Price Summary for DD/MM/YYYY`), parses `"Rate","Trades","Volume","Value"`, sorts by `Volume DESC` (tie-breaker: `Trades DESC`, `Rate DESC`, and flags any volume ties in `import_issues`), and selects ranks `1..5`.
  - Appends new date blocks into `top5_volume_records` (idempotent on `(trade_date, ticker, rank)`).
  - UI View **Volume and Rate** displays interactive date/ticker selectors, Top 5 table (`Rank`, `Rate`, `Volume`, `Trades`), historical top-volume rate trend chart, and one-click `.xlsx` export reproducing the exact 23-sheet workbook with `MM/DD/YYYY` titles, Excel tables (`T_{TICKER}_Block{N}`), autofilters, and Volume conditional data bars.

### 2.2 Module B: Multi-Account Trading, Profit & Performance Management
- **Legacy Process**: Uploading `TradeLog-DD-MM-YYYY_ALL.txt` to an LLM to update `Trade_Summary_Account_91404.xlsx` and `Trade_Summary_Account_91269.xlsx`.
- **Unified Dashboard Workflow**:
  - Parser reads each row, inspects the `Account` column (`91404` vs `91269`), and routes unknown accounts to `import_issues` (`UNEXPECTED_ACCOUNT`) without polluting `91404` or `91269`.
  - Deduplicates executions using `(account_id, execution_id)` (or composite key fallback).
  - Normalizes `Buy → BUY`, `Sell → SELL`, and `Short Sell → SELL` (while retaining `raw_side` in `trade_executions`).
  - Applies sell-side commission slabs at the execution level before aggregating:
    - Price `< 54.00`: `Quantity × 0.0175 / 100` PKR
    - Price `>= 54.00`: `TradeValue × 0.000325` PKR
    - SST = `Commission × 0.13`
  - Recomputes symbol-date summaries and period rollups (`Daily Summary`, `MTD`, `QTD`, `YTD`, `Monthly Summary`, `Yearly Summary`, `Symbol Performance`, `Dashboard`) from the canonical history.
  - Exports account-specific `.xlsx` workbooks (`Trade_Summary_Account_91404.xlsx` and `Trade_Summary_Account_91269.xlsx`) containing all 10 legacy sheets plus `Trade Log` and `Data Checks`.

### 2.3 Module C: Futures Comparison & Annualized Analysis
- **Legacy Process**: Maintaining `Futures_Analysis (3).xlsx` from `2026F` and `2026` cash data.
- **Unified Dashboard Workflow**:
  - Parses contract symbol `<BASE>-<CONTRACT>` (e.g., `ATRL-AUG`, `ATRL-AUGB`, `OGDC-SEP`, `OGDC-SEPB`, `PSO-OCTB`) dynamically, keeping `AUG` vs `AUGB` and `SEP` vs `SEPB` strictly separate.
  - Matches `(trade_date, base_symbol)` against `equity_ohlcv` for the **exact same date**. If either Current Value or Future Value is missing on that date, outputs `N/A` (never forward-fills).
  - Computes `Difference = Future - Current`, `Difference % = (Difference / Current) * 100`, and `Annualized % = (Difference / Current) * 365 / Days` sorted by `Annualized % ASC`.
  - Provides all 7 views in the **Futures Analysis** tab and exports the strict 8-sheet workbook (7 visible + 1 hidden `Data` sheet).

### 2.4 Module D: Technical Analysis & 36-Ticker Dashboard
- **Legacy Process**: Maintaining `PSX_RSI_Pivot_Analysis (4).xlsx` across 531 summary tickers and 36 detailed ticker tabs.
- **Unified Dashboard Workflow**:
  - Computes indicators from `equity_ohlcv` (`2026.xlsx`/`2026_YEAR.xlsx`) for all 531 tickers and detailed views for all 36 core tickers.
  - Displays searchable universe table + rich per-ticker interactive workspace (candlestick/OHLC + Bollinger + EMA chart, volume chart, RSI/MACD panels, Classic/Fibonacci/Camarilla daily pivots, previous-completed-week pivots, explainable composite signal & reference entry/stop/target levels).
  - Exports the legacy-compatible `PSX_RSI_Pivot_Analysis.xlsx` workbook.
