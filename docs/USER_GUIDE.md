# User Guide — PSX Trading Intelligence Dashboard

## 1. Overview & Local-First Design
The **PSX Trading Intelligence Dashboard** is a local-first web application that consolidates four legacy Excel/script workflows into a single browser-accessible terminal backed by a canonical SQLite database (`psx_data/database/app.db`):
1. **Module A**: Daily Top 5 Volume & Rate Register (`PSX_Top5_Volume_Rate_Register.xlsx`)
2. **Module B**: Multi-Account Trading, Profit & Performance Management for **Account 91404** and **Account 91269** (`Trade_Summary_Account_91404.xlsx` and `Trade_Summary_Account_91269.xlsx`)
3. **Module C**: Futures Comparison & Annualized Analysis (`Futures_Analysis.xlsx`)
4. **Module D**: Technical Analysis & 36-Ticker Dashboard (`PSX_RSI_Pivot_Analysis.xlsx`)

> **No LLM or Cloud Dependency**: Daily file uploads, parsing, deduplication, commission/SST calculations, futures spreads, technical indicators, and Excel workbook exports run 100% locally via deterministic Python code.

---

## 2. Launching the Application

### On Windows 11
Double-click `start_dashboard.bat` in the project root folder. It automatically starts the local FastAPI server on `http://127.0.0.1:8000` and opens your default browser.

### From Command Line (Windows / Linux / macOS)
```bash
python3 -m uvicorn psx_app.main:app --host 0.0.0.0 --port 8000
```

---

## 3. Daily Operational Workflow: Uploading New Files

1. Click **02 • Import and Update Center** in the left sidebar (or click **+ Upload Files** in the top bar).
2. Select or drag-and-drop one or more files (`.txt`, `.csv`, `.xlsx`, `.xls`, or `.zip`):
   - **Daily Ticker Price Summary `.txt` files** (e.g., `ATRL.txt`, `OGDC.txt`, or a `.zip` containing all daily ticker `.txt` files) → Routed to **Module A (Top 5 Register)**.
   - **Broker TradeLog `.txt` / `.csv` / `.xlsx` files** (e.g., `TradeLog-17-10-2026_ALL.txt`) → Routed to **Module B**, automatically splitting executions between **Account 91404** and **Account 91269** while isolating any unexpected accounts.
   - **Cash Equity OHLCV (`2026.xlsx` / `2026_compare.csv`), Futures OHLCV (`2026F.xlsx` / `2026F.csv`), or Index OHLCV (`INDEX.xlsx`)** → Routed to **Modules C & D**.
3. **Review the Staged Preview Card**:
   - Before touching your database, the system displays detected file types, date ranges, account IDs, rows read, new records to insert, exact duplicates to skip, and any source revisions or validation warnings.
4. Click **✓ Import and Update Canonical Database**:
   - All changes are committed in a single atomic SQLite transaction.
   - Raw files are archived with SHA-256 hashes under `psx_data/data/raw/`.
   - All affected dashboards, summaries, and technical caches are immediately updated.

---

## 4. Navigating the 10 Sidebar Sections

1. **01 • Overview Dashboard**: High-level KPIs across all 4 modules, side-by-side (never mixed) snapshots of Account 91404 and Account 91269, Top 5 volume highlights, Futures spread highlights, and Core 36 technical signal counts.
2. **02 • Import and Update Center**: Stage, preview, and atomically commit new files; inspect full import batch history.
3. **03 • Top 5 Volume & Rate Register**: Filter by ticker, date range, or search term; inspect the interactive Top 5 Volume & Rank-1 Rate chart; browse chronological `MM/DD/YYYY` blocks (`Rank, Rate, Volume, Trades`).
4. **04 • Account 91404 Performance**: Dedicated ledger for Account `91404` (`Dashboard`, `Daily Summary`, `Daily Detail` by date, `MTD/QTD/YTD`, `Monthly & Yearly Summary`, `Symbol Performance`, `Trade Log`, `Data Checks`).
5. **05 • Account 91269 Performance**: Dedicated ledger for Account `91269` (`Dashboard`, `Daily Summary`, `Daily Detail` by date, `MTD/QTD/YTD`, `Monthly & Yearly Summary`, `Symbol Performance`, `Trade Log`, `Data Checks`).
6. **06 • Futures Comparison & Annualized**: All 7 required views (`Monthly Comparison`, `Month Filter`, `Symbol Filter`, `Annualized Comparison`, `Date Filter`, `Future Symbol Summary`, `Date Summary`) plus editable `Days to Expiry` (default `30`) and `2-Month Rolling Retention` preview.
7. **07 • Technical Analysis & 36-Ticker**: Core 36-Ticker Matrix (including `MLCF (MLF)`), interactive Ticker Deep-Dive with SVG price/EMA/Bollinger/RSI chart, Daily Classic/Fibonacci/Camarilla pivots, Weekly pivots, 9-factor explainable signal & trade plan, and full 531-symbol screener.
8. **08 • Data Quality & Reconciliation**: Live reconciliation status against legacy workbooks, unmatched futures contracts (`Current Value = N/A`), and indicator history sufficiency checks.
9. **09 • Exports and Reports**: One-click download of all 5 formatted `.xlsx` workbooks and `.csv` extracts, plus built-in viewer for `/docs/*.md` and `/skills/catalog.json`.
10. **10 • Settings and Backup**: Edit commission slabs, SST %, default futures days, or rolling window months (with automatic rule versioning) and create/restore verified SQLite `.zip` backups.
