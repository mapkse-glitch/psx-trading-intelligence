# PSX Trading Intelligence Dashboard (Local-First Consolidated Platform v1.1)

A unified, audit-grade, local-first web application (Python FastAPI + Vanilla JS SPA + SQLite WAL + OpenPyXL) consolidating four legacy Pakistan Stock Exchange (PSX) spreadsheet workflows plus two interactive AI/Quantitative Trading Intelligence cards into a single institutional terminal.

---

## Quick Answers: Storage, Browser Access & Multi-Device Sync

- **Where is my data stored (in one line)?**
  All canonical historical and updated data, account ledgers (`91404` & `91269`), settings, backups, and Excel workbooks are stored in **`/home/user/psx_data/database/app.db`** (with raw files in `/home/user/psx_data/data/raw/`, backups in `/home/user/psx_data/backups/`, and Excel exports in `/home/user/psx_data/exports/`).
- **How to open over your browser:**
  Click the **"Open in new tab" (↗)** button on the live preview window in Arena, or on your own PC double-click `start_dashboard.bat` and open **`http://127.0.0.1:8000`**.
- **How to move/sync updated data (Office ↔ Home ↔ Phone):**
  See [`docs/CLOUD_HOSTING_AND_SYNC_GUIDE.md`](docs/CLOUD_HOSTING_AND_SYNC_GUIDE.md) for the complete guide covering **1-Click Backup `.zip` Restore**, **Google Drive / OneDrive shared `PSX_DATA_DIR`**, **Tailscale Mobile Access**, and **100% Free URL Hosting comparisons (GitHub, Vercel, Hugging Face Spaces, Cloudflare Tunnel)**.

---

## Interactive Trading Intelligence Cards (New in v1.1)

Available immediately on **01 • Overview & AI Setup Cards** and inside **07 • Technical Analysis & 36-Ticker**:

1. **Card 1 — Trading Ideas Generator (`GET /api/intelligence/trading-ideas`)**:
   - *“Scan today's market and generate 5 high-probability trading setups for [insert stock/index/sector]. Include entry price, exit targets, stop-loss, and risk/reward ratio. Explain why each setup works based on technical and fundamental factors.”*
   - Scans across **Core 36 Institutional Watchlist**, **Top 5 Volume Register Leaders**, **Deliverable Futures Universe**, **10 PSX Sectors** (Oil & Gas E&P, Refinery/OMC, Cement, Banking, Fertilizer, Power, Tech, Auto, Pharma, Telecom), or **all 531 PSX Cash Equities**.
2. **Card 2 — Automated Technical Analyst (`GET /api/intelligence/automated-analyst/{symbol}`)**:
   - *“Analyze [insert action/ticker] using daily and weekly charts. Break down support/resistance levels, trend lines, moving averages, and momentum indicators. Provide a step-by-step trading signal (Buy/Hold/Sell) with justification.”*
   - Computes multi-timeframe **Daily + Weekly OHLCV charts**, **20-day Linear Regression Trend Line slope & channel**, **Classic/Fibonacci/Camarilla Daily & Weekly Pivots**, **EMA 9/21/50/200 + Weekly SMA 4/10 alignment**, and a **5-step trading signal** with justification.

---

## Core Modules Consolidated

1. **Module A — Daily Top 5 Volume & Rate Register**:
   - Auto-detects PSX ticker `.txt` files (`\ufeff<SYMBOL> Price Summary for DD/MM/YYYY...`) and `.zip` archives.
   - Ranks valid rows by `Volume` descending per ticker/date and stores Top 5 rows (`Rank`, `Rate`, `Volume`, `Trades`) with `MM/DD/YYYY` date headers.
2. **Module B — Multi-Account Trading, Profit & Performance Management (`91404` & `91269`)**:
   - Strict account isolation between **Account 91404** (`36` trading days, `57` symbols, YTD Net P&L **`193,263.61 PKR`**) and **Account 91269** (`20` trading days, `31` symbols, YTD Net P&L **`35,658.95 PKR`**).
   - Exact PSX two-slab sell commission (`< 54.00 PKR` -> `0.0175 paisa/share`; `>= 54.00 PKR` -> `0.0325%` of sell value) and `13%` Sindh Sales Tax (SST).
3. **Module C — Futures Comparison & Annualized Analysis**:
   - Dynamic base/contract symbol parser (`KAPCO-OCTB` -> `KAPCO` + `OCTB`).
   - Exact same-date cash vs futures matching (`N/A` when missing, zero carry-forward), sorted by `Annualized %` ascending, 7 interactive views + 8-sheet `.xlsx` export (`Data` hidden).
4. **Module D — Technical Analysis & 36-Ticker Dashboard**:
   - 36 core tickers (`MLCF` canonical, `MLF -> MLCF` alias supported) + full 531-symbol PSX universe screener.
   - Wilder RSI(14), MACD(12,26,9), Bollinger Bands(20,2), EMA(9,21,50,200), Daily & Weekly Pivots, ADX(14), Typical Price & 20D VWAP, and 9-factor explainable signal engine.

---

## Clean Workspace Directory Layout

```text
/home/user/
├── psx_app/                      # FastAPI backend, parsers, services, SQLite schema & SPA frontend
├── psx_data/                     # Active runtime storage (Database, Backups, Exports, Raw Archive)
│   ├── database/app.db           # Canonical SQLite WAL database (100% migrated & reconciled)
│   ├── backups/                  # Verified .zip database backups with SHA-256 manifests
│   ├── exports/                  # Generated legacy-compatible .xlsx workbooks
│   └── data/raw/                 # Immutable raw archive of imported files
├── drive_mirror/                 # Untouched mirror of all 33 Google Drive files + SHA-256 manifests
├── docs/                         # 15 engineering, reconciliation, manual & cloud hosting documents
├── skills/                       # 16 verified local SKILL.md packages & security catalog
├── tests/                        # 16 automated pytest unit, integration & parity tests
├── start_dashboard.bat           # 1-click Windows launcher
└── start_dashboard.sh            # Linux/macOS launcher
```
