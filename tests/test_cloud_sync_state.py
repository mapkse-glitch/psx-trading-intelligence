from psx_app.services.cloud_sync_service import CloudSyncService, _LAST_SYNC_RESULT
from psx_app.database.schema import get_connection


def _cleanup_sync_state():
    conn = get_connection()
    conn.execute("DELETE FROM sync_state")
    conn.commit()
    conn.close()


def test_sync_state_health_toggle_survives_cold_start(monkeypatch):
    svc = CloudSyncService()
    svc.token = "test-token"
    svc.repo = "owner/repo"
    assert svc.is_configured()

    # 1. Simulate a 403 failure (token without Contents: Read-and-write)
    def boom(method, endpoint, payload=None):
        raise RuntimeError("GitHub 403 Forbidden: token lacks write permission")

    monkeypatch.setattr(svc, "_gh_request", boom)
    res = svc.push_db_after_update("test-fail")
    assert res["pushed"] is False
    st = svc.get_status()
    assert st["health"] == "PENDING"
    assert "403" in st["last_error"]

    # 2. Token fixed -> push succeeds -> health flips to ACTIVE
    def ok(method, endpoint, payload=None):
        if endpoint == "": return {"private": True}
        if endpoint.startswith("/git/ref"):
            return {"object": {"sha": "a" * 40}}
        if method == "GET" and endpoint.startswith("/git/commits/"):
            return {"tree": {"sha": "b" * 40}}
        if method == "GET" and endpoint.startswith("/git/trees/"):
            return {"tree": []}
        if endpoint == "/git/blobs":
            return {"sha": "c" * 40}
        if endpoint == "/git/trees":
            return {"sha": "d" * 40}
        if endpoint == "/git/commits":
            return {"sha": "e" * 40}
        return {}

    monkeypatch.setattr(svc, "_gh_request", ok)
    svc._save_base(initialized=True, blob=None, pending=True, repo=svc.repo, branch=svc.branch)
    res2 = svc.push_db_after_update("test-ok")
    assert res2["pushed"] is True
    st2 = svc.get_status()
    assert st2["health"] == "ACTIVE"
    assert st2["last_error"] is None

    # 3. Cold start: in-memory diagnostics lost, DB persists -> still ACTIVE
    _LAST_SYNC_RESULT.clear()
    svc2 = CloudSyncService()
    svc2.token = "test-token"
    svc2.repo = "owner/repo"
    st3 = svc2.get_status()
    assert st3["health"] == "ACTIVE"
    assert st3["last_push_ok"]
    assert st3["last_push_sha"] == "e" * 40

    _cleanup_sync_state()
