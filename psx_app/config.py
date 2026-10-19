import os
import gzip
import shutil
from pathlib import Path
from typing import Dict, Any, List

APP_ROOT = Path(__file__).resolve().parent
BASE_DIR = APP_ROOT.parent
DOCS_DIR = BASE_DIR / "docs"
SKILLS_DIR = BASE_DIR / "skills"
BUNDLED_DATA_ROOT = BASE_DIR / "psx_data"

# On Vercel or serverless read-only filesystems, automatically use /tmp/psx_data as writable storage
_IS_SERVERLESS = bool(
    os.environ.get("VERCEL")
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    or not os.access(str(BASE_DIR), os.W_OK)
)
_DEFAULT_DATA_DIR = "/tmp/psx_data" if _IS_SERVERLESS else (
    str(BUNDLED_DATA_ROOT) if BUNDLED_DATA_ROOT.exists() else str(BASE_DIR)
)

DATA_ROOT = Path(os.environ.get("PSX_DATA_DIR", _DEFAULT_DATA_DIR))
DRIVE_MIRROR_DIR = Path(os.environ.get("PSX_DRIVE_MIRROR", str(BASE_DIR / "drive_mirror")))

DB_DIR = DATA_ROOT / "database"
RAW_DIR = DATA_ROOT / "data" / "raw"
STAGING_DIR = DATA_ROOT / "data" / "staging"
PROCESSED_DIR = DATA_ROOT / "data" / "processed"
EXPORTS_DIR = DATA_ROOT / "exports"
BACKUPS_DIR = DATA_ROOT / "backups"
LOGS_DIR = DATA_ROOT / "logs"
CONFIG_DIR = DATA_ROOT / "config"

DB_PATH = Path(os.environ.get("PSX_DB_PATH", str(DB_DIR / "app.db")))

CORE_36_TICKERS: List[str] = [
    "ATRL", "DGKC", "GAL", "GHNI", "LUCK", "MLCF", "NBP", "NRL", "NML",
    "NPL", "NCPL", "OGDC", "PSO", "PPL", "PRL", "SEARL", "THCCL", "TRG",
    "BOP", "CPHL", "PTC", "SNGP", "SSGC", "NETSOL", "FFC", "UBL", "HBL",
    "SYS", "MUGHAL", "ISL", "INIL", "HUBC", "PSX", "SAZEW", "ENGROH", "PAEL"
]

TOP5_DEFAULT_TICKERS: List[str] = [
    "ATRL", "BOP", "CPHL", "DGKC", "FCCL", "GAL", "GHNI", "LUCK", "MLCF",
    "NBP", "NCPL", "NML", "NPL", "NRL", "OGDC", "PIOC", "PPL", "PRL",
    "PSO", "PTC", "SEARL", "THCCL", "TRG"
]

TICKER_ALIASES: Dict[str, str] = {
    "MLF": "MLCF",
}

AUTHORIZED_ACCOUNTS: List[str] = ["91404", "91269"]

DEFAULT_SETTINGS: Dict[str, Any] = {
    "commission_slab1_upper": 53.99999,
    "commission_slab1_paisa_per_share": 0.0175,
    "commission_slab2_start": 54.0,
    "commission_slab2_rate": 0.000325,
    "sst_rate": 0.13,
    "paisa_per_pkr": 100.0,
    "currency": "PKR",
    "futures_default_days": 30,
    "futures_rolling_retention_months": 2,
    "futures_apply_rolling_window": True,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bb_period": 20,
    "bb_std": 2.0,
    "ema_periods": [9, 21, 50, 200],
    "adx_period": 14,
    "strict_indicator_sufficiency": True,
    "signal_buy_threshold": 3,
    "signal_sell_threshold": -2,
    "signal_short_threshold": -5,
    "date_display_format": "YYYY-MM-DD",
    "top5_export_date_format": "MM/DD/YYYY",
    "backup_retention_count": 20,
    "saved_column_mappings": {},
    "rule_version": 1,
}


def ensure_directories(root: Path = DATA_ROOT) -> None:
    for sub in [
        root / "database",
        root / "data" / "raw",
        root / "data" / "staging",
        root / "data" / "processed",
        root / "exports",
        root / "backups",
        root / "logs",
        root / "config",
    ]:
        sub.mkdir(parents=True, exist_ok=True)

    target_db = root / "database" / "app.db"
    if not target_db.exists() or target_db.stat().st_size < 65536:
        # 1. Prioritize latest_cloud_sync.db.gz (which gets updated on GitHub after every daily import)
        for cand_gz in [
            BASE_DIR / "latest_cloud_sync.db.gz",
            BUNDLED_DATA_ROOT / "backups" / "latest_cloud_sync.db.gz",
            BASE_DIR / "backups" / "latest_cloud_sync.db.gz",
        ]:
            if cand_gz.exists():
                target_db.write_bytes(gzip.decompress(cand_gz.read_bytes()))
                return

        # 2. Fallback to bundled raw app.db
        for cand_db in [
            BUNDLED_DATA_ROOT / "database" / "app.db",
            BASE_DIR / "database" / "app.db",
        ]:
            if cand_db.exists() and cand_db.resolve() != target_db.resolve() and cand_db.stat().st_size >= 65536:
                shutil.copy2(str(cand_db), str(target_db))
                return
