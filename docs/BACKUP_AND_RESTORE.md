> Legacy reference: deployment and Section 07 behavior have changed. Current instructions: ../UPGRADE_1_3_7.md and SECTION07_RELIABILITY.md. Older fixture-specific statements are not a report of your current database.

# Backup and Restore Guide

## 1. Local Storage & Database Architecture
All application state is stored locally under `PSX_DATA_DIR` (defaults to `/home/user/psx_data` in the workspace or `%LOCALAPPDATA%\PSXTradingDashboard\` on Windows 11):
- `database/app.db`: Primary SQLite database configured with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`.
- `data/raw/`: Immutable archive of every uploaded source file prefixed with its SHA-256 hash.
- `backups/`: Verified `.zip` backup archives (`psx_backup_<YYYYMMDD_HHMMSS>_<label>.zip`).
- `exports/`: Generated `.xlsx` and `.csv` reports.

---

## 2. How Safe Online Backups Work
Never copy a live SQLite WAL database (`app.db`) using a plain OS file copy while transactions may be in flight. Instead, `BackupService` (`psx_app/services/backup_service.py`) uses Python's `sqlite3.Connection.backup()` online backup API:
1. Opens a consistent snapshot into a temporary `app.db` file.
2. Executes `PRAGMA integrity_check;` on the snapshot to verify zero page/index corruption.
3. Computes the SHA-256 hash of `app.db` and writes `manifest.json`:
   ```json
   {
     "backup_id": "psx_backup_20261018_174208_post_migration_verified",
     "created_at": "2026-10-18T17:42:08.924190+00:00",
     "label": "post_migration_verified",
     "db_size_bytes": 19509248,
     "db_sha256": "08e45f627f582309eae4d235022a1946d63e89749fa7dd14295844a708b16fb0",
     "integrity_ok": true
   }
   ```
4. Packages `app.db` and `manifest.json` (plus `data/raw/` if `include_raw_archive=True`) into a compressed `.zip` archive in `psx_data/backups/`.
5. Enforces configurable backup retention (default: keeps the 20 most recent backup archives).

---

## 3. Creating a Backup
### Via the Web UI
1. Navigate to **10 • Settings and Backup**.
2. Click **+ Create New Backup (.zip)**.
3. Click **Download** next to any backup row to save a copy to an external drive or folder.

### Via Python / CLI
```bash
python3 -c "from psx_app.services.backup_service import BackupService; print(BackupService().create_backup('manual_cli'))"
```

---

## 4. Restoring from a Backup
### Via the Web UI
1. Navigate to **10 • Settings and Backup**.
2. Click **Restore** next to the desired backup archive.
3. The system automatically:
   - Extracts the backup to a temporary directory.
   - Verifies that the SHA-256 hash of `app.db` matches `manifest.json`.
   - Runs `PRAGMA integrity_check;` on the extracted database.
   - Creates a `pre_restore_safety` backup of your current database before overwriting.
   - Atomically copies the restored database into `database/app.db` using `sqlite3.Connection.backup()`.
