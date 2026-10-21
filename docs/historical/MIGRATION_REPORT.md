> **Historical documentation (pre-1.3).** Preserved for project continuity, not current deployment instructions. Where this conflicts with README.md or DEPLOY_1_3.md, use the 1.3 documents. Old absolute paths, public-hosting advice, fixed dataset counts, probability wording and blanket reconciliation claims are superseded.

# Historical Data Migration & Legacy-to-New Reconciliation Report

## 1. Executive Summary
All **33 accessible files** from the Google Drive repository (`https://drive.google.com/drive/folders/1B_RBUoLcigiLxdnFYdg4xTgHHT1pSVFr?usp=sharing`) were inventoried, downloaded with SHA-256 verification into `/home/user/drive_mirror/`, and migrated into the canonical SQLite database (`/home/user/psx_data/data/app.db`) through the deterministic `MigrationService` (`psx_app/services/migration_service.py`).

- **Pre-migration SQLite backup**: `psx_backup_20261018_174152_pre_migration_initial.zip` (`integrity_ok = true`)
- **Post-migration SQLite backup**: `psx_backup_20261018_174208_post_migration_verified.zip` (`19,509,248` bytes uncompressed DB, `5,637,364` bytes compressed ZIP, SHA-256 `7678662a659d68db38e1708d7905bdf81e3700157e1e7943bc318b202dd56d7a`, `integrity_ok = true`)
- **Reconciliation Status across all 4 Modules**: **100% MATCH**

---

## 2. Migration Batches Executed

| Batch ID | Batch UUID | Source Label | Files Processed | Rows Read | New Canonical Records | Exact Duplicates Ignored | Revisions Logged | Status |
|---|---|---|---|---|---|---|---|---|
| `1` | `fd1e66c6-3055-4ca8-8a16-87d3b421b682` | Historical Migration — Legacy Workbooks Baseline | `3` | `5,100` | `5,100` | `0` | `0` | `COMMITTED` |
| `2` | `83649a9f-7058-43df-81c8-1eb3ecacf0e3` | Historical Migration — Raw TXT & TradeLog (16-Oct-2026) | `24` | `4,281` | `32` | `115` | `0` | `COMMITTED` |
| `3` | `e9af5a48-d3e5-4217-94ba-2913b023e509` | Historical Migration — Market OHLCV (Cash, Futures & Index) | `4` | `200,171` | `104,398` | `95,773` | `0` | `COMMITTED` |

### Why Duplicate Counts Occurred (Verified Deduplication Proof)
1. **Batch 2 (`115` duplicates ignored)**:
   - The 23 raw ticker `.txt` files in `Input folder/` (`ATRL.txt` .. `TRG.txt`, `4,249` raw trade-level rows) rank to `23 * 5 = 115` Top 5 records for `2026-10-16`.
   - Those 115 records matched the `10/16/2026` block already migrated from `PSX_Top5_Volume_Rate_12-08-2026_to_16-10-2026 (1).xlsx` in Batch 1 with **zero discrepancies**, so all 115 were safely skipped as exact duplicates.
   - Meanwhile, `TradeLog-16-10-2026_ALL.txt` contributed **32 raw trade executions** for Account `91404` on `2026-10-16` and upgraded the `2026-10-16` symbol summaries (`NRL-OCT`, `PPL-OCTB`, `PRL`, `PSO-OCTB`, `TRG-OCT`) from `LEGACY_MIGRATED` to `RAW_EXECUTIONS` provenance without double-counting!
2. **Batch 3 (`95,773` duplicates ignored)**:
   - `2026.xlsx` (`95,773` rows) and `2026_YEAR.xlsx` (`95,773` rows) contain identical Cash Equity OHLCV records across `196` trading dates (`2026-01-01` to `2026-10-16`) and `531` symbols.
   - Importing `2026.xlsx` inserted `95,773` records; importing `2026_YEAR.xlsx` verified and ignored all `95,773` identical `(trade_date, symbol)` records.
   - `2026F.xlsx` inserted `6,204` Futures OHLCV records (`52` trading dates, `387` contracts), and `INDEX.xlsx` inserted `2,421` KSE-100 Index OHLCV records (`2017-01-03` to `2026-10-16`).

---

## 3. Canonical Database State After Migration

| Table | Canonical Rows | Distinct Entities | Date Coverage |
|---|---|---|---|
| `top5_volume_records` | `4,805` | `23` Tickers (`961` ticker-date blocks) | `2026-08-12` to `2026-10-16` |
| `trade_executions` | `32` | Account `91404` (`5` symbols on `16-Oct-2026`) | `2026-10-16` |
| `account_daily_symbol_summary` | `295` | Account `91404` (`229` rows, `36` days, `57` symbols) & Account `91269` (`66` rows, `20` days, `31` symbols) | `2026-08-17` to `2026-10-16` |
| `equity_ohlcv` | `95,773` | `531` Cash Equity Symbols (`196` sessions) | `2026-01-01` to `2026-10-16` |
| `futures_ohlcv` | `6,204` | `387` Futures Contracts (`52` sessions) | `2026-08-04` to `2026-10-16` |
| `index_ohlcv` | `2,421` | `1` Benchmark Index (`KSE100`) | `2017-01-03` to `2026-10-16` |
| `source_files` | `31` | Archived in `/home/user/psx_data/data/raw/` | — |

---

## 4. Legacy-to-New Reconciliation Results

### 4.1 Module A — Top 5 Volume & Rate Register
- **Target**: `Output folder/PSX_Top5_Volume_Rate_12-08-2026_to_16-10-2026 (1).xlsx` vs 23 raw `.txt` files for `16/10/2026`.
- **Rows Compared**: `115` (`23` tickers × `5` ranks on `10/16/2026`) + `4,805` historical rows across `961` blocks.
- **Mismatches**: **`0`** (`status = MATCH`).

### 4.2 Module B — Multi-Account Trading & Performance (`91404` and `91269`)
| Metric | Account `91404` (Legacy) | Account `91404` (Unified App) | Diff | Account `91269` (Legacy) | Account `91269` (Unified App) | Diff |
|---|---|---|---|---|---|---|
| **YTD Buy Value (PKR)** | `403,231,367.88` | `403,231,367.88` | `0.00` | `74,766,195.21` | `74,766,195.21` | `0.00` |
| **YTD Sell Value (PKR)** | `403,570,742.02` | `403,570,742.02` | `0.00` | `74,829,034.33` | `74,829,034.33` | `0.00` |
| **YTD Gross P&L (PKR)** | `339,374.14` | `339,374.14` | `0.00` | `62,839.12` | `62,839.12` | `0.00` |
| **YTD Commission (PKR)** | `129,301.3531565` | `129,301.3531565` | `0.00` | `24,053.24465725` | `24,053.24465725` | `0.00` |
| **YTD SST 13% (PKR)** | `16,809.1759103` | `16,809.1759103` | `0.00` | `3,126.9218054` | `3,126.9218054` | `0.00` |
| **YTD Net P&L (PKR)** | `193,263.6109332` | `193,263.6109332` | `< 1e-9` | `35,658.9535373` | `35,658.9535373` | `0.00` |

### 4.3 Module C — Futures Comparison & Annualized Analysis
- **Target**: `Output folder/Futures_Analysis (3).xlsx` (`2026-10-16`, `Days = 30`).
- **Matched Rows on `2026-10-16`**: `98` contracts (`126` total futures rows on `2026-10-16`, of which `98` have same-date cash equity rows in `2026.xlsx` and `28` are displayed with `N/A` Current Value rather than backfilled).
- **Lowest Annualized % Row**: `KAPCO` (`OCTB`), Current Value `26.54`, Future Value `25.50`, Difference `-1.04`, Annualized % `-47.6765%` — **Exact Match** (`status = MATCH`).

### 4.4 Module D — Technical Analysis & 36-Ticker Dashboard (`ATRL` on `2026-10-16`)
| Indicator | Legacy (`PSX_RSI_Pivot_Analysis (4).xlsx`) | Unified App (`TechnicalService`) | Status |
|---|---|---|---|
| **Close** | `1219.10` | `1219.10` | Exact Match |
| **RSI (14, Wilder)** | `63.21` | `63.21` | Exact Match |
| **MACD (12,26,9)** | `26.54 / 27.55 / -1.01` | `26.54 / 27.55 / -1.01` | Exact Match |
| **Bollinger Bands (20,2)** | `1237.32 / 1181.35 / 1125.37` | `1237.32 / 1181.35 / 1125.37` | Exact Match |
| **EMA 9 / 21 / 50** | `1199.85 / 1177.77 / 1121.94` | `1199.85 / 1177.77 / 1121.94` | Exact Match |
| **EMA 200 (Recursive vs Strict)** | `951.04` (196 bars recursive) | `951.04` (recursive) / `null` (strict `< 200` bars) | Documented & Dual-Tracked |
| **ADX (14)** | `41.03` | `41.03` | Exact Match |
