# Canonical Data Dictionary

This document specifies the observed source schemas and the canonical SQLite database tables that power all four modules of the **Unified PSX Trading Intelligence Dashboard**.

---

## 1. Observed Source File Schemas

### 1.1 Daily Ticker Price Summary TXT (`Input folder/{TICKER}.txt`)
- **Header Line (Line 1)**: `^\ufeff?([A-Z0-9]+)\s+Price Summary for\s+(\d{2}/\d{2}/\d{4})\s+as per\s+(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2}:\d{2})`
- **Body Lines (CSV, quoted)**:
  - Column 0 (`rate`): `DECIMAL` (e.g., `"1,221.17"` → `1221.17`) — Execution price in PKR.
  - Column 1 (`trades`): `INTEGER` (e.g., `"220"` → `220`) — Number of trades at that rate.
  - Column 2 (`volume`): `INTEGER` (e.g., `"89051"` → `89051`) — Total share volume at that rate.
  - Column 3 (`traded_value`): `DECIMAL` (e.g., `"24,423.40"`) — Retained in raw parse audit only; excluded from the Top 5 Register table per specification.

### 1.2 Broker TradeLog TXT (`Input folder/TradeLog-DD-MM-YYYY_ALL.txt`)
- **Header Line (Line 1)**: `Daily Trade Log for (\d{2}/\d{2}/\d{4}), from (\d{2}:\d{2}:\d{2}) to (\d{2}:\d{2}:\d{2}) as per (\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}:\d{2})`
- **Body Lines (18 Quoted CSV Fields)**:
  - Col 0 (`terminal_id`): e.g. `"THM00601"`
  - Col 1 (`market_type`): e.g. `"FUT"`, `"Reg"`
  - Col 2 (`symbol`): e.g. `"NRL-OCT"`, `"PRL"`, `"PSO-OCTB"`
  - Col 3 (`account_id`): e.g. `"91404"`, `"91269"`
  - Col 4 (`client_ref`): `""`
  - Col 5 (`trade_time`): `HH:MM:SS` (e.g. `"09:37:29"`)
  - Col 6 (`order_id`): e.g. `"00600R00062"`
  - Col 7 (`status`): e.g. `"Filled"`
  - Col 8 (`raw_side`): `"Buy"`, `"Sell"`, `"Short Sell"`
  - Col 9 (`quantity`): Executed shares (`INTEGER`, e.g. `500`)
  - Col 10 (`remaining_qty`): Remaining order shares (`INTEGER`, e.g. `500`)
  - Col 11 (`order_qty`): Total order shares (`INTEGER`, e.g. `1000`)
  - Col 12 (`price`): Execution price in PKR (`DECIMAL`, e.g. `666.48`)
  - Col 13 (`field_13`): `""`
  - Col 14 (`execution_id`): Unique broker ticket/execution reference (e.g. `"0101000000264880"`)
  - Col 15–16: `""`
  - Col 17 (`trade_value`): Execution value in PKR (`DECIMAL`, e.g. `333240.00`)

### 1.3 Daily Cash & Futures OHLCV (`2026.xlsx`, `2026_YEAR.xlsx`, `2026F.xlsx`)
- **Columns**:
  - `DATE`: Trading date (`YYYY-MM-DD`)
  - `SYMBOL`: Base symbol in `2026.xlsx` (e.g. `OGDC`, `ATRL`) or contract symbol in `2026F.xlsx` (e.g. `OGDC-AUG`, `ATRL-AUGB`, `PSO-OCTB`)
  - `VOLUME`: Daily traded volume (`INTEGER`)
  - `PR-CLOSE`: Previous session close (`DECIMAL`)
  - `HIGH`: Session high (`DECIMAL`)
  - `LOW`: Session low (`DECIMAL`)
  - `OPEN`: Session open (`DECIMAL`)
  - `CLOSE`: Session close (`DECIMAL`)
  - `AVG`: Session average price (`DECIMAL`)

---

## 2. Canonical SQLite Database Tables

### 2.1 Provenance, Staging & Audit Tables
- `source_files`: `id`, `filename`, `file_type`, `sha256_hash`, `file_size`, `archive_path`, `detected_date_min`, `detected_date_max`, `uploaded_at`, `status`
- `import_batches`: `id`, `batch_uuid`, `created_at`, `committed_at`, `status` (`STAGED`, `COMMITTED`, `ROLLED_BACK`, `FAILED`), `files_count`, `rows_read`, `rows_accepted`, `new_records`, `duplicates_ignored`, `revisions_count`, `rows_rejected`, `warnings_count`, `summary_json`
- `import_issues`: `id`, `batch_id`, `source_file_id`, `module`, `severity` (`INFO`, `WARNING`, `ERROR`), `issue_type`, `symbol`, `account_id`, `trade_date`, `row_number`, `message`, `raw_payload`
- `source_revisions`: `id`, `batch_id`, `table_name`, `business_key`, `old_value_json`, `new_value_json`, `reason`, `recorded_at`
- `audit_events`: `id`, `event_type`, `actor`, `details_json`, `created_at`
- `app_settings`: `key`, `value_json`, `description`, `version`, `updated_at`

### 2.2 Module A Table (`top5_volume_records`)
- `id` (`INTEGER PRIMARY KEY`)
- `trade_date` (`TEXT`, ISO `YYYY-MM-DD`)
- `ticker` (`TEXT`)
- `rank` (`INTEGER`, `1..5`)
- `rate` (`REAL`)
- `volume` (`INTEGER`)
- `trades` (`INTEGER`)
- `snapshot_time` (`TEXT`, metadata only — excluded from legacy export table)
- `source_file_id` (`INTEGER`)
- `batch_id` (`INTEGER`)
- `imported_at` (`TEXT`)
- **Unique Constraint**: `UNIQUE(trade_date, ticker, rank)`

### 2.3 Module B Tables (`accounts`, `trade_executions`, `account_daily_symbol_summary`)
- `accounts`: `account_id` (`TEXT PRIMARY KEY`, e.g. `'91404'`, `'91269'`), `terminal_id`, `label`, `currency`, `is_authorized` (`INTEGER`)
- `trade_executions`:
  - `id`, `account_id`, `trade_date`, `trade_time`, `terminal_id`, `market_type`, `symbol`, `raw_side`, `normalized_side` (`BUY` / `SELL`), `order_id`, `execution_id`, `status`, `quantity`, `remaining_qty`, `order_qty`, `price`, `trade_value`, `commission_slab`, `commission_amount`, `sst_amount`, `total_charges`, `unique_trade_key`, `source_file_id`, `batch_id`, `imported_at`
  - **Unique Constraint**: `UNIQUE(account_id, unique_trade_key)`
- `account_daily_symbol_summary`:
  - Stores canonical symbol-date aggregations (both migrated historical blocks from `2026-08-17`..`2026-10-15` where raw execution logs were not present in Drive, and live recalculated aggregations from `trade_executions`).
  - Columns: `account_id`, `trade_date`, `symbol`, `market_type`, `buy_qty`, `buy_value`, `avg_buy_price`, `sell_qty`, `sell_value`, `avg_sell_price`, `price_diff`, `net_qty`, `gross_pnl`, `commission_slab_label`, `commission_amount`, `sst_amount`, `total_charges`, `net_pnl`, `return_on_buy`, `origin_type` (`RAW_EXECUTIONS` vs `LEGACY_MIGRATED`), `source_filename`, `batch_id`
  - **Unique Constraint**: `UNIQUE(account_id, trade_date, symbol)`

### 2.4 Module C & Module D Market Data Tables (`equity_ohlcv`, `futures_ohlcv`, `index_ohlcv`, `indicator_cache`)
- `equity_ohlcv`: `trade_date`, `symbol`, `volume`, `pr_close`, `high`, `low`, `open`, `close`, `avg_price`, `source_file_id`, `batch_id` — `UNIQUE(trade_date, symbol)`
- `futures_ohlcv`: `trade_date`, `contract_symbol` (e.g. `OGDC-OCTB`), `base_symbol` (`OGDC`), `contract_month` (`OCTB`), `volume`, `pr_close`, `high`, `low`, `open`, `close`, `avg_price`, `change_val` (`close - pr_close`), `source_file_id`, `batch_id` — `UNIQUE(trade_date, contract_symbol)`
- `index_ohlcv`: `trade_date`, `pr_close`, `open`, `high`, `low`, `close`, `source_file_id`, `batch_id` — `UNIQUE(trade_date)`
- `indicator_cache`: `symbol`, `trade_date`, `settings_version`, `rsi14`, `macd`, `macd_sig`, `macd_hist`, `bb_up`, `bb_mid`, `bb_low`, `pct_b`, `bb_width`, `ema9`, `ema21`, `ema50`, `ema200`, `ema200_sufficient`, `vwap_typical_daily`, `vwap_rolling20`, `adx14`, `plus_di`, `minus_di`, `daily_pivot_json`, `weekly_pivot_json`, `signal_score`, `signal_action`, `signal_json`, `updated_at` — `UNIQUE(symbol, trade_date, settings_version)`
