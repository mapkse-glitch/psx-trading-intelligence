from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from psx_app.config import DATA_ROOT, DB_PATH, DRIVE_MIRROR_DIR
from psx_app.database.schema import get_connection, init_db
from psx_app.services.backup_service import BackupService
from psx_app.services.import_orchestrator import ImportOrchestrator
from psx_app.services.reconciliation_service import ReconciliationService


class MigrationService:
    """
    Layer 9 — Historical Data Migration & Deduplication Service.
    Migrates all accessible files from the Google Drive mirror into the canonical SQLite DB.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        data_root: Optional[Path] = None,
        drive_mirror: Optional[Path] = None,
    ):
        self.db_path = db_path or DB_PATH
        self.data_root = data_root or DATA_ROOT
        self.drive_mirror = drive_mirror or DRIVE_MIRROR_DIR
        self.orchestrator = ImportOrchestrator(self.db_path, self.data_root)
        self.backup_service = BackupService(self.db_path, self.data_root)
        self.reconciliation = ReconciliationService(self.db_path, self.drive_mirror)

    def run_initial_migration(self, force: bool = False) -> Dict[str, Any]:
        init_db(self.db_path)

        with get_connection(self.db_path) as c:
            eq_cnt = c.execute("SELECT COUNT(*) FROM equity_ohlcv").fetchone()[0]
            top5_cnt = c.execute("SELECT COUNT(*) FROM top5_volume_records").fetchone()[0]
            if eq_cnt > 0 and top5_cnt > 0 and not force:
                return {
                    "status": "ALREADY_MIGRATED",
                    "equity_ohlcv_rows": eq_cnt,
                    "top5_rows": top5_cnt,
                    "reconciliation": self.reconciliation.reconcile_against_legacy_workbooks(),
                }

        in_dir = self.drive_mirror / "Input folder"
        out_dir = self.drive_mirror / "Output folder"
        if not in_dir.exists() or not out_dir.exists():
            return {
                "status": "DRIVE_MIRROR_NOT_FOUND",
                "message": f"Expected Google Drive mirror at {self.drive_mirror}.",
            }

        # Step 0: Create pre-migration backup
        pre_backup = self.backup_service.create_backup(label="pre_migration_initial")

        batches_executed: List[Dict[str, Any]] = []

        # Batch 1: Historical Baselines from Output folder workbooks (Top 5 history + Account 91404 & 91269 histories)
        # Note: For Account 91404, we also have raw TradeLog-16-10-2026_ALL.txt in Input folder, which will overwrite
        # the 2026-10-16 symbol summaries with RAW_EXECUTIONS provenance without double-counting!
        baseline_files: List[Tuple[str, bytes]] = []
        for fn in [
            "PSX_Top5_Volume_Rate_12-08-2026_to_16-10-2026 (1).xlsx",
            "Trade_Summary_Account_91269_Updated_2026-10-15.xlsx",
            "Trade_Summary_Account_91404_Updated_2026-10-16.xlsx",
        ]:
            p = out_dir / fn
            if p.exists():
                baseline_files.append((fn, p.read_bytes()))

        if baseline_files:
            staged_b1 = self.orchestrator.stage_uploaded_files(
                baseline_files, source_label="Historical Migration — Legacy Workbooks Baseline"
            )
            committed_b1 = self.orchestrator.commit_staged_batch(staged_b1["batch_uuid"])
            batches_executed.append(committed_b1)

        # Batch 2: Raw Daily Top 5 TXT files (23 files for 16/10/2026) + Raw TradeLog-16-10-2026_ALL.txt
        raw_daily_files: List[Tuple[str, bytes]] = []
        for p in sorted(in_dir.glob("*.txt")):
            raw_daily_files.append((p.name, p.read_bytes()))

        if raw_daily_files:
            staged_b2 = self.orchestrator.stage_uploaded_files(
                raw_daily_files, source_label="Historical Migration — Raw TXT & TradeLog (16-Oct-2026)"
            )
            committed_b2 = self.orchestrator.commit_staged_batch(staged_b2["batch_uuid"])
            batches_executed.append(committed_b2)

        # Batch 3: Primary Market OHLCV Workbooks (2026.xlsx, 2026_YEAR.xlsx, 2026F.xlsx, INDEX.xlsx)
        market_files: List[Tuple[str, bytes]] = []
        for fn in ["2026.xlsx", "2026_YEAR.xlsx", "2026F.xlsx", "INDEX.xlsx"]:
            p = in_dir / fn
            if p.exists():
                market_files.append((fn, p.read_bytes()))

        if market_files:
            staged_b3 = self.orchestrator.stage_uploaded_files(
                market_files, source_label="Historical Migration — Market OHLCV (Cash, Futures & Index)"
            )
            committed_b3 = self.orchestrator.commit_staged_batch(staged_b3["batch_uuid"])
            batches_executed.append(committed_b3)

        # Warm up technical indicator cache for Core 36 tickers
        self.reconciliation.technical_service.get_universe_summary(scope="core36")

        post_backup = self.backup_service.create_backup(label="post_migration_verified")
        recon = self.reconciliation.reconcile_against_legacy_workbooks()

        return {
            "status": "MIGRATION_COMPLETED",
            "pre_backup": pre_backup,
            "post_backup": post_backup,
            "batches": [
                {
                    "batch_uuid": b["batch_uuid"],
                    "source_label": b["source_label"],
                    "files_count": b["files_count"],
                    "rows_read": b["rows_read"],
                    "new_records": b["new_records"],
                    "duplicates_ignored": b["duplicates_ignored"],
                    "revisions_count": b["revisions_count"],
                }
                for b in batches_executed
            ],
            "reconciliation": recon,
        }
