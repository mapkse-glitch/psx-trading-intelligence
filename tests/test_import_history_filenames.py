from pathlib import Path
import os
import shutil
from fastapi.testclient import TestClient
from psx_app.main import app
from psx_app.config import RAW_DIR
from psx_app.database.schema import get_connection


def _cleanup_batch(b_uuid: str) -> None:
    conn = get_connection()
    row = conn.execute("SELECT id, status FROM import_batches WHERE batch_uuid=?", (b_uuid,)).fetchone()
    if row:
        conn.execute("DELETE FROM import_issues WHERE batch_id=?", (row["id"],))
        conn.execute("DELETE FROM source_revisions WHERE batch_id=?", (row["id"],))
        conn.execute("DELETE FROM import_batches WHERE id=?", (row["id"],))
        conn.commit()
    conn.close()
    shutil.rmtree(RAW_DIR / b_uuid, ignore_errors=True)


def test_audit_history_exposes_filenames_and_staged_resumable_flags():
    client = TestClient(app)
    atrl_bytes = open(str(Path(os.environ["PSX_TEST_REFERENCE_DIR"]) / "Input folder" / "ATRL.txt"), "rb").read()

    res_stage = client.post(
        "/api/imports/stage",
        files=[("files", ("ATRL.txt", atrl_bytes, "text/plain"))],
    )
    assert res_stage.status_code == 200
    staged = res_stage.json()

    res_hist = client.get("/api/imports/history")
    assert res_hist.status_code == 200
    batches = res_hist.json()["batches"]
    match = [b for b in batches if b["batch_uuid"] == staged["batch_uuid"]]
    assert len(match) == 1
    assert match[0]["filenames"] == ["ATRL.txt"]
    assert match[0]["staged_resumable"] is True

    res_commit = client.post(
        "/api/imports/commit",
        json={"batch_uuid": staged["batch_uuid"], "allow_revisions": True},
    )
    assert res_commit.status_code == 200
    assert res_commit.json()["status"] == "COMMITTED"

    res_hist2 = client.get("/api/imports/history")
    match2 = [b for b in res_hist2.json()["batches"] if b["batch_uuid"] == staged["batch_uuid"]]
    assert len(match2) == 1
    assert match2[0]["filenames"] == ["ATRL.txt"]
    assert match2[0]["status"] == "COMMITTED"
    assert match2[0]["staged_resumable"] is False

    _cleanup_batch(staged["batch_uuid"])


def test_discard_staged_batch_and_protect_committed_data():
    client = TestClient(app)
    atrl_bytes = open(str(Path(os.environ["PSX_TEST_REFERENCE_DIR"]) / "Input folder" / "ATRL.txt"), "rb").read()

    res_stage = client.post(
        "/api/imports/stage",
        files=[("files", ("ATRL.txt", atrl_bytes, "text/plain"))],
    )
    staged = res_stage.json()

    res_discard = client.post(
        "/api/imports/discard",
        json={"batch_uuid": staged["batch_uuid"], "allow_revisions": True},
    )
    assert res_discard.status_code == 200
    assert res_discard.json()["discarded"] is True
    assert res_discard.json()["previous_status"] == "STAGED"

    res_hist = client.get("/api/imports/history")
    match = [b for b in res_hist.json()["batches"] if b["batch_uuid"] == staged["batch_uuid"]]
    assert len(match) == 0

    res_stage2 = client.post(
        "/api/imports/stage",
        files=[("files", ("ATRL.txt", atrl_bytes, "text/plain"))],
    )
    staged2 = res_stage2.json()
    res_commit = client.post(
        "/api/imports/commit",
        json={"batch_uuid": staged2["batch_uuid"], "allow_revisions": True},
    )
    assert res_commit.status_code == 200
    res_discard2 = client.post(
        "/api/imports/discard",
        json={"batch_uuid": staged2["batch_uuid"], "allow_revisions": True},
    )
    assert res_discard2.status_code == 400

    res_commit_again = client.post(
        "/api/imports/commit",
        json={"batch_uuid": staged2["batch_uuid"], "allow_revisions": True},
    )
    assert res_commit_again.status_code == 200
    assert res_commit_again.json()["status"] == "ALREADY_COMMITTED"

    _cleanup_batch(staged2["batch_uuid"])
