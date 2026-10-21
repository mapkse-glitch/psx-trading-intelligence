> **Historical documentation (pre-1.3).** Preserved for project continuity, not current deployment instructions. Where this conflicts with README.md or DEPLOY_1_3.md, use the 1.3 documents. Old absolute paths, public-hosting advice, fixed dataset counts, probability wording and blanket reconciliation claims are superseded.

# System Requirements Specification — Unified PSX Trading Intelligence Dashboard

## 1. Executive Summary & Mission

The **Unified PSX Trading Intelligence Dashboard** is a local-first, deterministic web application built for the Pakistan Stock Exchange (PSX) that consolidates four previously separate LLM-maintained Excel workflows into a single auditable platform backed by a persistent SQLite database:

1. **Module A — Daily Top 5 Volume & Rate Register**: Automated parsing of PSX ticker price-summary `.txt` files (`ATRL.txt`, `PRL.txt`, etc.), ranking records by `Volume` descending, extracting the top 5 rows (`Rank`, `Rate`, `Volume`, `Trades`), maintaining the historical register across 23+ tickers, and exporting the multi-sheet Excel register with `mm/dd/yyyy` block headers and Excel tables.
2. **Module B — Multi-Account Trading, Profit & Performance Management**: Automated ingestion of `TradeLog-*.txt`/`.csv`/`.xlsx` files, strict separation of **Account 91404** and **Account 91269** (plus isolation of unexpected accounts), composite execution-key deduplication, execution-level PSX commission slab calculation (`< 54 PKR` = `0.0175 paisa/share`, `>= 54 PKR` = `0.0325%` of sell value), `13%` SST, gross/net P&L, Return on Buy, and full Daily, MTD, QTD, YTD, Monthly, Yearly, Symbol Performance, Trade Log, Settings, Data Checks, and Import Audit reporting.
3. **Module C — Futures Comparison & Annualized Analysis**: Dynamic matching of cash/spot equity prices (`2026.xlsx` / `2026_YEAR.xlsx` / `2026_compare.csv`) with PSX futures contracts (`2026F.xlsx` / `2026F.csv`) across contract months (`JAN`–`DEC` plus suffix variants `AUGB`, `SEPB`, `OCTB`, etc.), strict same-date matching (never forward-filling missing dates; displaying `N/A`), configurable `Days` input (default `30`), configurable 2-month rolling retention policy with preview, all 7 required views (`Monthly Comparison`, `Month Filter`, `Symbol Filter`, `Annualized Comparison`, `Date Filter`, `Future Symbol Summary`, `Date Summary`), and 8-sheet Excel workbook export (7 visible + 1 hidden `Data` sheet).
4. **Module D — Technical Analysis & 36-Ticker Dashboard**: Full daily OHLCV storage and indicator calculation engine across all 531 PSX tickers and deep-dive dashboards for the 36 core tickers (`ATRL`, `DGKC`, `GAL`, `GHNI`, `LUCK`, `MLCF`, `NBP`, `NRL`, `NML`, `NPL`, `NCPL`, `OGDC`, `PSO`, `PPL`, `PRL`, `SEARL`, `THCCL`, `TRG`, `BOP`, `CPHL`, `PTC`, `SNGP`, `SSGC`, `NETSOL`, `FFC`, `UBL`, `HBL`, `SYS`, `MUGHAL`, `ISL`, `INIL`, `HUBC`, `PSX`, `SAZEW`, `ENGROH`, `PAEL`), computing Wilder's `RSI(14)`, `MACD(12,26,9)`, `Bollinger Bands(20,2)`, `EMA 9/21/50/200`, `Daily Typical-Price VWAP Proxy`, `ADX(14)` with `+DI/-DI`, Daily Pivots (Classic, Fibonacci, Camarilla), Previous-Completed-Week Pivots, and an explainable rule-based signal & reference-level engine.

---

## 2. Core Functional Requirements

### FR-1: Local-First Deterministic Operation
- Runs locally on Windows (and Linux/macOS) via Python FastAPI + SQLite + browser UI without any LLM API, cloud subscription, or external market feed.
- Binds to `127.0.0.1` by default on Windows (`start_dashboard.bat`), with configurable host/port via environment variables for preview or private server deployment.

### FR-2: Unified Upload, Staging, Validation & Atomic Import
- Supports single-file, multi-file, and `.zip` archive uploads, plus one-click import from the local mirror of the Google Drive reference folder.
- Auto-detects file type:
  - `TOP5_TXT`: PSX Price Summary `.txt` files (`{TICKER} Price Summary for DD/MM/YYYY...`)
  - `TRADELOG`: Broker trade log `.txt`/`.csv`/`.xlsx` (`Daily Trade Log for DD/MM/YYYY...`)
  - `OHLCV_CASH`: Cash/spot market daily OHLCV (`2026.xlsx`, `2026_YEAR.xlsx`, `2026_compare.csv`)
  - `OHLCV_FUTURES`: Futures market daily OHLCV (`2026F.xlsx`, `2026F.csv`)
  - `INDEX_OHLCV`: Market benchmark index (`INDEX.xlsx`)
  - `LEGACY_WORKBOOK`: Existing output `.xlsx` workbooks for historical migration and reconciliation
- Generates a pre-commit **Import Preview** showing detected source type, dates, accounts, symbols, row counts, duplicate counts, and validation warnings before writing to production tables.
- Enforces **SHA-256 content-hash idempotency** and business-key deduplication so re-importing the same file never double-counts records.

### FR-3: Persistent Storage, Raw File Archival & Safe Backups
- Stores SQLite database (`database/app.db`), raw uploaded files (`data/raw/`), staging payloads (`data/staging/`), exports (`exports/`), and backups (`backups/`).
- Uses SQLite `backup()` API for safe online backups, pre-migration automatic snapshots, integrity checks (`PRAGMA integrity_check`), and user-triggered restore with confirmation.

### FR-4: Legacy-Compatible Excel Exports
- Generates and downloads verified `.xlsx` workbooks for all four workflows with pre-calculated values AND Excel formulas so workbooks open immediately with accurate numbers in any viewer.
