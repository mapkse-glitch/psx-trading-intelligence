import base64
import gzip
import json
import os
import shutil
import sqlite3
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from psx_app.config import DB_PATH, BACKUPS_DIR


# In-memory diagnostic of the most recent push/pull attempt (per serverless instance)
_LAST_SYNC_RESULT: Dict[str, Any] = {}


class CloudSyncService:
    """
    Zero-Cost Cloud Persistence Sync Engine for Vercel Free Hosting.
    When GITHUB_SYNC_REPO ('mapkse-glitch/psx-trading-intelligence') and GITHUB_SYNC_TOKEN
    are configured in Vercel Environment Variables:
      1. Every import commit / settings update / backup restore compresses app.db (~5.8 MB .gz)
         using SQLite's online backup API and commits it to 'latest_cloud_sync.db.gz' in the
         GitHub repository via the GitHub Git Data API.
      2. On cold start, the service pulls 'latest_cloud_sync.db.gz' from GitHub so new serverless
         instances always boot with your latest daily imports.

    IMPORTANT for 403 Forbidden errors: the GitHub token must have WRITE permission:
      - Classic Personal Access Token: enable the 'repo' scope; OR
      - Fine-grained PAT: select this repository -> Permissions -> Contents: Read and Write
        (Metadata: Read is added automatically).
    """

    REMOTE_FILE_PATH = "latest_cloud_sync.db.gz"

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.repo = os.environ.get("GITHUB_SYNC_REPO", "mapkse-glitch/psx-trading-intelligence").strip()
        self.token = os.environ.get("GITHUB_SYNC_TOKEN", "").strip()
        self.branch = os.environ.get("GITHUB_SYNC_BRANCH", "main").strip() or "main"

    def is_configured(self) -> bool:
        return bool(self.repo and self.token and "/" in self.repo)

    # ------------------------------------------------------------------
    # Persistent sync state (sync_state table). Survivorship rules:
    #  * last_push_attempt is written BEFORE the snapshot is created, so any
    #    snapshot that reaches GitHub carries this marker -> a hydrated cold
    #    start KNOWS that push succeeded (otherwise the snapshot would not exist).
    #  * last_error(_at) is only written on real failures; health = ERROR only
    #    when the newest marker overall is an error.
    # ------------------------------------------------------------------
    def _state_read(self) -> Dict[str, str]:
        try:
            conn = sqlite3.connect(str(self.db_path))
            try:
                rows = conn.execute("SELECT key, value FROM sync_state").fetchall()
            except sqlite3.OperationalError:
                return {}
            finally:
                conn.close()
            return {k: (v or "") for k, v in rows}
        except Exception:
            return {}

    def _state_write(self, updates: Dict[str, str]) -> None:
        try:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS sync_state (key TEXT PRIMARY KEY, value TEXT)")
                for k, v in updates.items():
                    conn.execute(
                        "INSERT INTO sync_state(key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (k, v if v is not None else ""),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        local_sync_file = BACKUPS_DIR / "latest_cloud_sync.db.gz"
        st = self._state_read()

        mem_err = _LAST_SYNC_RESULT.get("error") or ""
        mem_err_at = _LAST_SYNC_RESULT.get("error_at") or ""
        mem_ok_at = _LAST_SYNC_RESULT.get("last_push") or ""

        err_txt = st.get("last_error", "")
        err_at = st.get("last_error_at", "")
        ok_at = st.get("last_push_ok", "")
        att_at = st.get("last_push_attempt", "")
        # An attempt marker inside a hydrated snapshot == that push succeeded remotely.
        effective_ok = max(ok_at, att_at, mem_ok_at)
        latest_err_at = max(err_at, mem_err_at)
        err_active = bool(latest_err_at) and latest_err_at > effective_ok
        err_msg = mem_err if (mem_err_at and mem_err_at >= err_at) else err_txt

        configured = self.is_configured()
        health = "LOCAL" if not configured else ("ERROR" if err_active else "ACTIVE")
        return {
            "enabled": configured,
            "provider": (
                f"GitHub Auto-Sync Active ({self.repo})"
                if configured
                else "Local / Ephemeral Mode (Add GITHUB_SYNC_TOKEN in Vercel Env Vars for Automatic GitHub Save)"
            ),
            "repo": self.repo or None,
            "branch": self.branch,
            "remote_path": self.REMOTE_FILE_PATH,
            "local_snapshot_exists": local_sync_file.exists(),
            "local_snapshot_size_bytes": local_sync_file.stat().st_size if local_sync_file.exists() else 0,
            "last_push": effective_ok or None,
            "last_push_ok": ok_at or None,
            "last_push_sha": st.get("last_push_sha") or None,
            "last_pull": _LAST_SYNC_RESULT.get("last_pull"),
            "last_error": (err_msg or None) if err_active else None,
            "health": health,
            "auto_push": "Every successful upload Commit automatically pushes the fresh snapshot to GitHub — no manual action needed.",
            "hint": (
                "If pushes return 403 Forbidden, your GITHUB_SYNC_TOKEN lacks write permission. "
                "Use a Classic token with the 'repo' scope, or a Fine-grained token limited to this repo "
                "with 'Contents: Read and write'. Then click 'Push Snapshot Now' once."
            ),
        }

    def create_local_gzip_snapshot(self) -> Path:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        out_gz = BACKUPS_DIR / "latest_cloud_sync.db.gz"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "app_snapshot.db"
            src = sqlite3.connect(str(self.db_path))
            dst = sqlite3.connect(str(tmp_db))
            with dst:
                src.backup(dst)
            dst.close()
            src.close()
            raw_bytes = tmp_db.read_bytes()
            comp_bytes = gzip.compress(raw_bytes, compresslevel=6)
            out_gz.write_bytes(comp_bytes)
        return out_gz

    def _gh_request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{self.repo}{endpoint}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PSX-Trading-Intelligence-Dashboard",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            code = e.code
            if code == 401:
                raise RuntimeError(
                    "GitHub 401 Unauthorized: your GITHUB_SYNC_TOKEN is invalid or expired. "
                    "Generate a NEW token on GitHub (Settings -> Developer settings -> Personal access tokens), "
                    "update the 'GITHUB_SYNC_TOKEN' variable in Vercel -> Settings -> Environment Variables, "
                    "and click 'Push Snapshot to GitHub Now'."
                ) from e
            if code == 403:
                raise RuntimeError(
                    f"GitHub 403 Forbidden: your GITHUB_SYNC_TOKEN has NO WRITE permission for '{self.repo}'. "
                    "Fix: create a Classic token with the full 'repo' scope, OR a Fine-grained token selecting ONLY "
                    f"this repository with Permissions -> 'Contents: Read and write' (Metadata: Read included). "
                    "Update the token in Vercel -> Settings -> Environment Variables and retry. "
                    "Your data is always safe locally too — use 'Download Updated latest_cloud_sync.db.gz'."
                ) from e
            if code == 404:
                raise RuntimeError(
                    f"GitHub 404 Not Found: repository '{self.repo}' (branch '{self.branch}') was not found. "
                    "Check the 'GITHUB_SYNC_REPO' environment variable matches your repo exactly, e.g. 'mapkse-glitch/psx-trading-intelligence'."
                ) from e
            body = ""
            try:
                body = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            raise RuntimeError(f"GitHub API error {code}: {(body or e.reason)[:200]}") from e

    def push_db_after_update(self, reason: str = "Automated update") -> Dict[str, Any]:
        configured = self.is_configured()
        attempt_iso = datetime.now(timezone.utc).isoformat()
        if configured:
            # Marker written BEFORE the snapshot is created: any snapshot that
            # lands on GitHub carries it, so every future cold start knows the
            # push it was hydrated from succeeded -> health stays ACTIVE and the
            # emergency "Push Snapshot" button stays hidden until a REAL failure.
            self._state_write({"last_push_attempt": attempt_iso})
        gz_path = self.create_local_gzip_snapshot()
        if not configured:
            _LAST_SYNC_RESULT["last_attempt"] = attempt_iso
            return {
                "pushed": False,
                "local_snapshot_updated": True,
                "size_bytes": gz_path.stat().st_size,
                "message": "Updated snapshot created in memory/disk. Set GITHUB_SYNC_TOKEN in Vercel Environment Variables to auto-commit to GitHub, or click 'Download latest_cloud_sync.db.gz'.",
            }

        try:
            b64_content = base64.b64encode(gz_path.read_bytes()).decode("ascii")
            ref_data = self._gh_request("GET", f"/git/ref/heads/{self.branch}")
            latest_commit_sha = ref_data["object"]["sha"]
            commit_data = self._gh_request("GET", f"/git/commits/{latest_commit_sha}")
            base_tree_sha = commit_data["tree"]["sha"]

            blob_data = self._gh_request("POST", "/git/blobs", {
                "content": b64_content,
                "encoding": "base64",
            })
            blob_sha = blob_data["sha"]

            tree_data = self._gh_request("POST", "/git/trees", {
                "base_tree": base_tree_sha,
                "tree": [{
                    "path": self.REMOTE_FILE_PATH,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }],
            })

            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            new_commit = self._gh_request("POST", "/git/commits", {
                "message": f"chore(db-sync): {reason} [{now_str}]",
                "tree": tree_data["sha"],
                "parents": [latest_commit_sha],
            })
            self._gh_request("PATCH", f"/git/refs/heads/{self.branch}", {
                "sha": new_commit["sha"],
                "force": False,
            })
            res = {
                "pushed": True,
                "commit_sha": new_commit["sha"],
                "size_bytes": gz_path.stat().st_size,
                "timestamp": now_str,
            }
            _LAST_SYNC_RESULT["last_push"] = attempt_iso
            _LAST_SYNC_RESULT.pop("error", None)
            _LAST_SYNC_RESULT.pop("error_at", None)
            self._state_write({
                "last_push_ok": attempt_iso,
                "last_push_sha": new_commit["sha"],
                "last_error": "",
                "last_error_at": "",
            })
            return res
        except Exception as exc:
            fail_iso = datetime.now(timezone.utc).isoformat()
            _LAST_SYNC_RESULT["last_attempt"] = fail_iso
            _LAST_SYNC_RESULT["error"] = str(exc)
            _LAST_SYNC_RESULT["error_at"] = fail_iso
            self._state_write({"last_error": str(exc), "last_error_at": fail_iso})
            return {
                "pushed": False,
                "local_snapshot_updated": True,
                "error": str(exc),
            }

    def pull_latest_db_on_startup(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"pulled": False, "reason": "GITHUB_SYNC_TOKEN not configured"}

        try:
            ref_data = self._gh_request("GET", f"/git/ref/heads/{self.branch}")
            commit_sha = ref_data["object"]["sha"]
            commit_data = self._gh_request("GET", f"/git/commits/{commit_sha}")
            tree_data = self._gh_request("GET", f"/git/trees/{commit_data['tree']['sha']}?recursive=1")

            target_sha = None
            for item in tree_data.get("tree", []):
                if item.get("path") in (self.REMOTE_FILE_PATH, "psx_data/backups/latest_cloud_sync.db.gz"):
                    target_sha = item.get("sha")
                    break

            if not target_sha:
                return {"pulled": False, "reason": "No remote latest_cloud_sync.db.gz found yet"}

            blob_data = self._gh_request("GET", f"/git/blobs/{target_sha}")
            comp_bytes = base64.b64decode(blob_data["content"])
            raw_db_bytes = gzip.decompress(comp_bytes)

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, dir=str(self.db_path.parent), suffix=".db") as tf:
                tf.write(raw_db_bytes)
                tmp_path = Path(tf.name)

            conn = sqlite3.connect(str(tmp_path))
            chk = conn.execute("PRAGMA integrity_check;").fetchone()[0]
            conn.close()
            if str(chk).lower() != "ok":
                tmp_path.unlink(missing_ok=True)
                return {"pulled": False, "reason": f"Remote DB integrity check failed: {chk}"}

            for ext in ["-wal", "-shm"]:
                p = Path(str(self.db_path) + ext)
                if p.exists():
                    p.unlink()
            shutil.move(str(tmp_path), str(self.db_path))
            _LAST_SYNC_RESULT["last_pull"] = datetime.now(timezone.utc).isoformat()
            return {"pulled": True, "blob_sha": target_sha, "bytes_restored": len(raw_db_bytes)}
        except Exception as exc:
            _LAST_SYNC_RESULT["error"] = str(exc)
            return {"pulled": False, "error": str(exc)}
