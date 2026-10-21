"""Isolated tests: never use a live database. Private reference fixtures are opt-in."""
import os
import sqlite3
import tempfile
from pathlib import Path
import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix='psx-tests-'))
REFERENCE_DB = os.environ.get('PSX_TEST_SEED_DB')
REFERENCE_DIR = os.environ.get('PSX_TEST_REFERENCE_DIR')
os.environ['PSX_DATA_DIR'] = str(TEST_ROOT)
os.environ['PSX_DB_PATH'] = str(TEST_ROOT / 'database' / 'app.db')
os.environ['PSX_DRIVE_MIRROR'] = REFERENCE_DIR or str(TEST_ROOT / 'absent-references')
os.environ['PSX_AUTH_DISABLED'] = '1'
os.environ.pop('GITHUB_SYNC_TOKEN', None)
os.environ.pop('VERCEL', None)
os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)
(TEST_ROOT / 'database').mkdir()
if REFERENCE_DB:
    with sqlite3.connect(REFERENCE_DB) as src, sqlite3.connect(os.environ['PSX_DB_PATH']) as dst:
        src.backup(dst)
from psx_app.database.schema import init_db
init_db(Path(os.environ['PSX_DB_PATH']))

REFERENCE_TESTS = {
 'test_top5_single_txt_parsing_and_volume_ranking', 'test_top5_service_and_legacy_excel_export',
 'test_account_91404_and_91269_strict_separation_and_reconciliation',
 'test_daily_summary_symbols_column_and_symbol_performance_dates_column',
 'test_futures_comparison_formulas_sorting_and_days_recalculation','test_futures_summaries_and_rolling_window',
 'test_futures_8_sheet_excel_export_structure','test_core_36_tickers_and_mlf_mlcf_alias',
 'test_atrl_indicators_pivots_and_no_future_leakage','test_insufficient_history_handling',
 'test_reconciliation_backup_and_fastapi_endpoints','test_incremental_upload_staging_and_idempotency',
 'test_futures_comparison_resolves_non_trading_calendar_date','test_date_summary_resolves_calendar_date_and_returns_ooc_note',
 'test_all_dates_modes_still_untouched_by_resolution','test_intelligence_cards_are_data_only_and_enriched',
 'test_audit_history_exposes_filenames_and_staged_resumable_flags','test_discard_staged_batch_and_protect_committed_data',
 'test_chunked_upload_produce_same_manifest_as_direct_stage','test_chunked_stage_reports_missing_chunks_and_recovers',
}

def pytest_collection_modifyitems(items):
    for item in items:
        if item.name in REFERENCE_TESTS and not (REFERENCE_DB and REFERENCE_DIR):
            item.add_marker(pytest.mark.skip(reason='Private historical reference fixtures not supplied; see docs/TESTING_1_3.md'))
