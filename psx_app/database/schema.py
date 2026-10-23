import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from psx_app.config import DB_PATH, DEFAULT_SETTINGS, AUTHORIZED_ACCOUNTS, ensure_directories

DDL_STATEMENTS = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS company_reference (list_name TEXT NOT NULL,symbol TEXT NOT NULL,company TEXT NOT NULL,sector TEXT NOT NULL,PRIMARY KEY(list_name,symbol));
CREATE TABLE IF NOT EXISTS reference_previews (token TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS forecast_ledger (forecast_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,as_of TEXT NOT NULL,horizon INTEGER NOT NULL,version TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,outcome_json TEXT,evaluated_revision TEXT,last_checked TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS forecast_observations (forecast_id TEXT NOT NULL,digest TEXT NOT NULL,outcome_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(forecast_id,digest));
CREATE INDEX IF NOT EXISTS idx_forecast_asof ON forecast_ledger(as_of,symbol);
CREATE TABLE IF NOT EXISTS learning_runs (run_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,as_of TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    archive_path TEXT NOT NULL,
    detected_date_min TEXT,
    detected_date_max TEXT,
    uploaded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ARCHIVED'
);
CREATE INDEX IF NOT EXISTS idx_source_files_hash ON source_files(sha256_hash);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_uuid TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    committed_at TEXT,
    status TEXT NOT NULL DEFAULT 'STAGED',
    source_label TEXT,
    files_count INTEGER NOT NULL DEFAULT 0,
    rows_read INTEGER NOT NULL DEFAULT 0,
    rows_accepted INTEGER NOT NULL DEFAULT 0,
    new_records INTEGER NOT NULL DEFAULT 0,
    duplicates_ignored INTEGER NOT NULL DEFAULT 0,
    revisions_count INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    warnings_count INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS import_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER,
    source_file_id INTEGER,
    module TEXT NOT NULL,
    severity TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    symbol TEXT,
    account_id TEXT,
    trade_date TEXT,
    row_number INTEGER,
    message TEXT NOT NULL,
    raw_payload TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(batch_id) REFERENCES import_batches(id),
    FOREIGN KEY(source_file_id) REFERENCES source_files(id)
);
CREATE INDEX IF NOT EXISTS idx_import_issues_module ON import_issues(module, severity);

CREATE TABLE IF NOT EXISTS source_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER,
    table_name TEXT NOT NULL,
    business_key TEXT NOT NULL,
    old_value_json TEXT NOT NULL,
    new_value_json TEXT NOT NULL,
    reason TEXT,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(batch_id) REFERENCES import_batches(id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'local_user',
    details_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

-- Persistent cloud-sync state (survives ephemeral /tmp resets once pushed to GitHub):
-- keys: last_push_attempt, last_push_ok, last_push_sha, last_error, last_error_at
CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- MODULE A: Top 5 Volume & Rate Register
CREATE TABLE IF NOT EXISTS top5_volume_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    rank INTEGER NOT NULL,
    rate REAL NOT NULL,
    volume INTEGER NOT NULL,
    trades INTEGER NOT NULL,
    snapshot_time TEXT,
    source_filename TEXT,
    source_file_id INTEGER,
    batch_id INTEGER,
    origin_type TEXT NOT NULL DEFAULT 'RAW_TXT',
    imported_at TEXT NOT NULL,
    UNIQUE(trade_date, ticker, rank)
);
CREATE INDEX IF NOT EXISTS idx_top5_date_ticker ON top5_volume_records(trade_date, ticker);
CREATE INDEX IF NOT EXISTS idx_top5_ticker_date ON top5_volume_records(ticker, trade_date);

-- MODULE B: Multi-Account Trading & P&L
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    terminal_id TEXT,
    label TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'PKR',
    is_authorized INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    trade_time TEXT,
    terminal_id TEXT,
    market_type TEXT,
    symbol TEXT NOT NULL,
    raw_side TEXT NOT NULL,
    normalized_side TEXT NOT NULL,
    order_id TEXT,
    execution_id TEXT,
    status TEXT,
    quantity INTEGER NOT NULL,
    remaining_qty INTEGER,
    order_qty INTEGER,
    price REAL NOT NULL,
    trade_value REAL NOT NULL,
    commission_slab TEXT,
    commission_amount REAL NOT NULL DEFAULT 0.0,
    sst_amount REAL NOT NULL DEFAULT 0.0,
    total_charges REAL NOT NULL DEFAULT 0.0,
    unique_trade_key TEXT NOT NULL,
    source_filename TEXT,
    source_file_id INTEGER,
    batch_id INTEGER,
    imported_at TEXT NOT NULL,
    UNIQUE(account_id, unique_trade_key)
);
CREATE INDEX IF NOT EXISTS idx_exec_acc_date ON trade_executions(account_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_exec_acc_sym ON trade_executions(account_id, symbol);

CREATE TABLE IF NOT EXISTS account_daily_symbol_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    market_type TEXT,
    buy_qty INTEGER NOT NULL DEFAULT 0,
    buy_value REAL NOT NULL DEFAULT 0.0,
    avg_buy_price REAL,
    sell_qty INTEGER NOT NULL DEFAULT 0,
    sell_value REAL NOT NULL DEFAULT 0.0,
    avg_sell_price REAL,
    price_diff REAL,
    net_qty INTEGER NOT NULL DEFAULT 0,
    gross_pnl REAL NOT NULL DEFAULT 0.0,
    commission_slab_label TEXT,
    commission_amount REAL NOT NULL DEFAULT 0.0,
    sst_amount REAL NOT NULL DEFAULT 0.0,
    total_charges REAL NOT NULL DEFAULT 0.0,
    net_pnl REAL NOT NULL DEFAULT 0.0,
    return_on_buy REAL,
    origin_type TEXT NOT NULL DEFAULT 'RAW_EXECUTIONS',
    source_filename TEXT,
    batch_id INTEGER,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, trade_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_adss_acc_date ON account_daily_symbol_summary(account_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_adss_acc_sym ON account_daily_symbol_summary(account_id, symbol);

-- MODULE C & D: Equity Cash OHLCV, Futures OHLCV & Index OHLCV
CREATE TABLE IF NOT EXISTS equity_ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    volume INTEGER NOT NULL DEFAULT 0,
    pr_close REAL,
    high REAL,
    low REAL,
    open REAL,
    close REAL NOT NULL,
    avg_price REAL,
    source_filename TEXT,
    source_file_id INTEGER,
    batch_id INTEGER,
    UNIQUE(trade_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_eq_sym_date ON equity_ohlcv(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_eq_date_sym ON equity_ohlcv(trade_date, symbol);

CREATE TABLE IF NOT EXISTS futures_ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    contract_symbol TEXT NOT NULL,
    base_symbol TEXT NOT NULL,
    contract_month TEXT NOT NULL,
    volume INTEGER NOT NULL DEFAULT 0,
    pr_close REAL,
    high REAL,
    low REAL,
    open REAL,
    close REAL NOT NULL,
    avg_price REAL,
    change_val REAL,
    source_filename TEXT,
    source_file_id INTEGER,
    batch_id INTEGER,
    UNIQUE(trade_date, contract_symbol)
);
CREATE INDEX IF NOT EXISTS idx_fut_date_base ON futures_ohlcv(trade_date, base_symbol);
CREATE INDEX IF NOT EXISTS idx_fut_date_month ON futures_ohlcv(trade_date, contract_month);
CREATE INDEX IF NOT EXISTS idx_fut_sym_date ON futures_ohlcv(contract_symbol, trade_date);

CREATE TABLE IF NOT EXISTS index_ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL UNIQUE,
    pr_close REAL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    source_filename TEXT,
    source_file_id INTEGER,
    batch_id INTEGER
);

CREATE TABLE IF NOT EXISTS indicator_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    rule_version INTEGER NOT NULL DEFAULT 1,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(symbol, trade_date, rule_version)
);
CREATE INDEX IF NOT EXISTS idx_ind_cache_sym ON indicator_cache(symbol, trade_date);

CREATE TABLE IF NOT EXISTS calculation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL DEFAULT 'ALL',
    rule_name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    parameters_json TEXT NOT NULL,
    effective_from TEXT,
    created_at TEXT NOT NULL
);
"""


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    from psx_app.database.turso import enabled, connect, ensure_ready
    if enabled():
        ensure_ready()
        return connect()
    target = Path(db_path) if db_path else DB_PATH
    ensure_directories(target.parent.parent)
    conn = sqlite3.connect(str(target), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    from psx_app.database.turso import enabled, ensure_ready
    if enabled():
        ensure_ready()
        return
    target = Path(db_path) if db_path else DB_PATH
    ensure_directories(target.parent.parent)
    # Auto-hydrate from latest_cloud_sync.db.gz if target DB does not exist yet
    if not target.exists() or target.stat().st_size < 65536:
        import gzip
        from psx_app.config import BUNDLED_DATA_ROOT
        for cand_gz in [
            target.parent.parent / "backups" / "latest_cloud_sync.db.gz",
            BUNDLED_DATA_ROOT / "backups" / "latest_cloud_sync.db.gz",
        ]:
            if cand_gz.exists():
                target.write_bytes(gzip.decompress(cand_gz.read_bytes()))
                break

    conn = get_connection(db_path)
    try:
        conn.executescript(DDL_STATEMENTS)
        now = datetime.now(timezone.utc).isoformat()
        for acc in AUTHORIZED_ACCOUNTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO accounts (account_id, terminal_id, label, currency, is_authorized, created_at)
                VALUES (?, 'THM00601', ?, 'PKR', 1, ?)
                """,
                (acc, f"Account {acc}", now),
            )
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO app_settings (key, value_json, description, version, updated_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (k, json.dumps(v), f"Setting: {k}", now),
            )
        conn.commit()
    finally:
        conn.close()
