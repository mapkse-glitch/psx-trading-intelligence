> **Historical documentation (pre-1.3).** Preserved for project continuity, not current deployment instructions. Where this conflicts with README.md or DEPLOY_1_3.md, use the 1.3 documents. Old absolute paths, public-hosting advice, fixed dataset counts, probability wording and blanket reconciliation claims are superseded.

# Automated Verification & Test Report (`pytest`)

## 1. Execution Summary
- **Test Runner**: `pytest 9.0.3` on Python `3.13.16`
- **Command**: `pytest -v` (configured via `/home/user/pytest.ini`)
- **Total Suites / Test Cases**: `4` test modules, `16` comprehensive integration & unit tests
- **Outcome**: **`16 PASSED, 0 FAILED` (`100% Pass Rate`)**
- **Execution Duration**: `4.51s`

---

## 2. Test Coverage Matrix by Module

### 2.1 Module A — Top 5 Volume & Rate Register (`tests/test_module_a_top5.py`)
| Test Case | Verified Requirement | Result |
|---|---|---|
| `test_top5_single_txt_parsing_and_volume_ranking` | Parses `ATRL.txt` (`16/10/2026`), extracts `mm/dd/yyyy = 10/16/2026`, ranks valid trade rows by `Volume DESC`, and verifies Rank 1 (`Rate = 1215.0`, `Volume = 89,051`, `Trades = 220`) against the legacy workbook. | **PASSED** |
| `test_top5_fewer_than_5_rows_and_invalid_row_rejection` | Verifies that tickers with `< 5` valid rows retain only valid rows (`1..3`) without inventing rows `4..5`, rejects negative/zero values (`NON_POSITIVE_VALUES`) and malformed lines, and logs `FEWER_THAN_5_ROWS`. | **PASSED** |
| `test_top5_tie_volume_detection` | Verifies deterministic tie-breaking (`Volume DESC, Trades DESC, Rate DESC`) and logs `VOLUME_TIE` in the audit trail. | **PASSED** |
| `test_top5_service_and_legacy_excel_export` | Verifies `Top5Service.get_register` and `ExportService.export_top5_workbook()` output structure: one sheet per ticker, `MM/DD/YYYY` date headers, strictly `Rank, Rate, Volume, Trades` columns, Excel tables, and conditional formatting data bars. | **PASSED** |

### 2.2 Module B — Multi-Account Trading & Performance (`tests/test_module_b_accounts.py`)
| Test Case | Verified Requirement | Result |
|---|---|---|
| `test_commission_slab1_slab2_boundary_and_sst` | Verifies Slab 1 (`Sell Rate < 54.00 PKR -> Sell Qty * 0.0175 / 100`), Slab 2 boundary at `Sell Rate == 54.00 PKR` (`Sell Value * 0.000325`), `SST = Commission * 13%`, `Total Charges = Commission + SST`, and zero commission on `BUY` executions. | **PASSED** |
| `test_tradelog_normalization_deduplication_and_unexpected_account_isolation` | Verifies `Short Sell -> SELL` normalization (preserving `raw_side = 'Short Sell'`), in-file duplicate execution skipping (`DUPLICATE_IN_FILE`), multiple partial fills allowed under the same `Order ID`, and isolation of unexpected accounts (`99999 -> UNEXPECTED_ACCOUNT`). | **PASSED** |
| `test_account_91404_and_91269_strict_separation_and_reconciliation` | Verifies strict account separation (`91404` has 36 trading days, `91269` has 20 trading days), exact `16-Oct-2026` totals for `91404` (`Net P&L = 8,766.7772275 PKR`), and `0.00` internal reconciliation diffs across Daily, MTD, QTD, YTD, Monthly, Yearly, and Symbol summaries. | **PASSED** |

### 2.3 Module C — Futures Comparison & Annualized Analysis (`tests/test_module_c_futures.py`)
| Test Case | Verified Requirement | Result |
|---|---|---|
| `test_dynamic_contract_symbol_splitting` | Verifies dynamic base symbol and contract suffix parsing (`ATRL-OCTB -> ATRL + OCTB`, `BOP-SEPB -> BOP + SEPB`) keeping suffix variants separate. | **PASSED** |
| `test_futures_comparison_formulas_sorting_and_days_recalculation` | Verifies `Difference`, `Difference %`, `Annualized %` (`KAPCO-OCTB = -47.6765%` at `Days = 30`), ascending `Annualized %` sort order across all 98 matched contracts on `2026-10-16`, and dynamic recalculation when `Days = 15`. | **PASSED** |
| `test_futures_summaries_and_rolling_window` | Verifies `Future Symbol Summary` (`Change = CLOSE - PR_CL`), `Date Summary` sorted by `SYMBOL ASC`, empty-date message (`No data available for this date.`), and 2-month rolling window retention (`2026-09-01` cutoff, `3,913` retained rows). | **PASSED** |
| `test_futures_8_sheet_excel_export_structure` | Verifies that `Futures_Analysis.xlsx` contains **strictly 7 visible worksheets** (`Monthly Comparison`, `Month Filter`, `Symbol Filter`, `Annualized Comparison`, `Date Filter`, `Future Symbol Summary`, `Date Summary`) and **1 hidden worksheet** (`Data`). | **PASSED** |

### 2.4 Module D, Migration, Staging, Backup & FastAPI (`tests/test_module_d_and_system.py`)
| Test Case | Verified Requirement | Result |
|---|---|---|
| `test_core_36_tickers_and_mlf_mlcf_alias` | Verifies all 36 core tickers are present and that `MLF` resolves transparently to `MLCF` (`Maple Leaf Cement Factory`). | **PASSED** |
| `test_atrl_indicators_pivots_and_no_future_leakage` | Verifies 100% numerical parity on `ATRL` (`2026-10-16`: `RSI14 = 63.21`, `MACD = 26.54 / 27.55 / -1.01`, `BB = 1237.32 / 1181.35 / 1125.37`, `EMA 9/21/50 = 1199.85 / 1177.77 / 1121.94`, `ADX = 41.03`, `Classic Pivot P = 1217.37`) and proves zero future-data leakage by comparing bar 150 of a truncated 150-bar series against bar 150 of the full 196-bar series. | **PASSED** |
| `test_insufficient_history_handling` | Verifies that a 9-bar series returns `rsi14 = None`, `macd = None`, and `action = 'INSUFFICIENT DATA'` rather than fabricating indicator values. | **PASSED** |
| `test_reconciliation_backup_and_fastapi_endpoints` | Verifies `MATCH` status across all 4 legacy workbooks, `PRAGMA integrity_check = ok`, and FastAPI `/api/health` & `/api/overview` responses. | **PASSED** |
| `test_incremental_upload_staging_and_idempotency` | Uploads `ATRL.txt` through `/api/imports/stage` and `/api/imports/commit`, confirming `5 duplicates_ignored` and `0 new_records` (100% idempotent). | **PASSED** |
