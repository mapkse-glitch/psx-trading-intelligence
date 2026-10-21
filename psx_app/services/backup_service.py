import hashlib
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from psx_app.config import DATA_ROOT, DB_PATH, ensure_directories
from psx_app.database.repository import Repository
from psx_app.database.schema import get_connection


class BackupService:
    """
    Layer 10 — SQLite-safe Online Backup, Verification, Retention & Restore Service.
    Uses sqlite3.Connection.backup() rather than raw file copy on a live WAL database.
    """

    def __init__(self, db_path: Optional[Path] = None, data_root: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.data_root = Path(data_root) if data_root else DATA_ROOT
        ensure_directories(self.data_root)
        self.backups_dir = self.data_root / "backups"
        self.repo = Repository(self.db_path)

    def run_integrity_check(self, target_db: Optional[Path] = None) -> Dict[str, Any]:
        db_file = target_db or self.db_path
        if not db_file.exists():
            return {"ok": False, "result": "DATABASE_FILE_NOT_FOUND"}
        conn = sqlite3.connect(str(db_file))
        try:
            res = conn.execute("PRAGMA integrity_check;").fetchall()
            messages = [r[0] for r in res]
            ok = messages == ["ok"]
            return {"ok": ok, "messages": messages, "db_path": str(db_file)}
        finally:
            conn.close()

    def create_backup(self, label: str = "manual", include_raw_archive: bool = False) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d_%H%M%S_%f")
        clean_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label)
        backup_name = f"psx_backup_{ts}_{clean_label}"
        work_dir = self.backups_dir / backup_name
        work_dir.mkdir(parents=True, exist_ok=True)

        snapshot_db_path = work_dir / "app.db"
        # Perform safe online SQLite backup
        src_conn = sqlite3.connect(str(self.db_path))
        dst_conn = sqlite3.connect(str(snapshot_db_path))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        integrity = self.run_integrity_check(snapshot_db_path)
        if not integrity["ok"]:
            raise ValueError("Backup integrity check failed; no valid backup was created.")
        db_bytes = snapshot_db_path.read_bytes()
        db_sha256 = hashlib.sha256(db_bytes).hexdigest()

        manifest = {
            "backup_id": backup_name,
            "created_at": now.isoformat(),
            "label": label,
            "db_size_bytes": len(db_bytes),
            "db_sha256": db_sha256,
            "integrity_ok": integrity["ok"],
            "include_raw_archive": include_raw_archive,
        }
        (work_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        zip_path = self.backups_dir / f"{backup_name}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot_db_path, arcname="app.db")
            zf.write(work_dir / "manifest.json", arcname="manifest.json")
            if include_raw_archive and (self.data_root / "data" / "raw").exists():
                for p in (self.data_root / "data" / "raw").rglob("*"):
                    if p.is_file():
                        zf.write(p, arcname=f"raw/{p.relative_to(self.data_root / 'data' / 'raw')}")

        shutil.rmtree(work_dir, ignore_errors=True)
        zip_sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()

        result = {
            **manifest,
            "zip_filename": zip_path.name,
            "zip_path": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": zip_sha256,
        }
        self._enforce_retention()
        self.repo.log_audit("BACKUP_CREATED", result)
        return result

    def list_backups(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for zp in sorted(self.backups_dir.glob("psx_backup_*.zip"), reverse=True):
            try:
                with zipfile.ZipFile(zp, "r") as zf:
                    m = json.loads(zf.read("manifest.json").decode("utf-8"))
                items.append({
                    **m,
                    "zip_filename": zp.name,
                    "zip_size_bytes": zp.stat().st_size,
                })
            except Exception as e:
                items.append({
                    "backup_id": zp.stem,
                    "zip_filename": zp.name,
                    "zip_size_bytes": zp.stat().st_size,
                    "integrity_ok": False,
                    "error": str(e),
                })
        return items

    def restore_backup(self, zip_filename: str, create_safety_backup: bool = True) -> Dict[str, Any]:
        zp = self.backups_dir / Path(zip_filename).name
        if not zp.exists():
            raise FileNotFoundError(f"Backup archive '{zip_filename}' not found.")

        temp_extract = self.backups_dir / f"_restore_tmp_{datetime.now(timezone.utc).strftime('%H%M%S')}"
        temp_extract.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                zf.extract("app.db", path=temp_extract)
                zf.extract("manifest.json", path=temp_extract)
            manifest = json.loads((temp_extract / "manifest.json").read_text(encoding="utf-8"))
            extracted_db = temp_extract / "app.db"
            actual_sha = hashlib.sha256(extracted_db.read_bytes()).hexdigest()
            if actual_sha != manifest.get("db_sha256"):
                raise ValueError("Backup SHA-256 verification failed; aborting restore.")
            chk = self.run_integrity_check(extracted_db)
            if not chk["ok"]:
                raise ValueError(f"Backup SQLite integrity check failed: {chk}")

            safety = None
            if create_safety_backup and self.db_path.exists():
                safety = self.create_backup(label="pre_restore_safety")

            # Use SQLite backup API to restore cleanly into self.db_path
            src_conn = sqlite3.connect(str(extracted_db))
            dst_conn = sqlite3.connect(str(self.db_path))
            try:
                with dst_conn:
                    src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            with sqlite3.connect(str(self.db_path)) as cache_conn:
                cache_conn.execute("DELETE FROM indicator_cache")
            self.repo.log_audit("BACKUP_RESTORED", {"restored_from": zip_filename, "safety_backup": safety})
            return {
                "status": "RESTORED",
                "restored_from": zip_filename,
                "manifest": manifest,
                "safety_backup": safety,
                "post_restore_integrity": self.run_integrity_check(self.db_path),
            }
        finally:
            shutil.rmtree(temp_extract, ignore_errors=True)

    def _enforce_retention(self) -> None:
        # User backups are retained until the owner explicitly removes them externally.
        return None
