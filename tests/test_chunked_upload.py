import pytest
from fastapi.testclient import TestClient
from psx_app.main import app
from tests.test_import_history_filenames import _cleanup_batch


def _chunk_payload(data: bytes, chunk_size: int = 1024
                   ) -> list:
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def test_chunked_upload_produce_same_manifest_as_direct_stage():
    client = TestClient(app)
    atrl_bytes = open("/home/user/drive_mirror/Input folder/ATRL.txt", "rb").read()
    pieces = _chunk_payload(atrl_bytes, chunk_size=64)
    uid = "testchunk0001-xx"

    for i, piece in enumerate(pieces):
        res = client.post(
            f"/api/imports/upload-chunk?upload_id={uid}&name=ATRL.txt&idx={i}&total={len(pieces)}",
            content=piece,
        )
        assert res.status_code == 200
        assert res.json()["stored"] is True

    res2 = client.post(
        "/api/imports/stage-chunked",
        json={"uploads": [{"upload_id": uid, "name": "ATRL.txt", "total_chunks": len(pieces)}]},
    )
    assert res2.status_code == 200
    staged = res2.json()
    assert staged["files_count"] == 1
    assert staged["duplicates_ignored"] == 5  # same unique-key dedup as a direct upload

    # chunk directory should have been cleaned up after assembly
    from psx_app.config import DATA_ROOT
    assert not (DATA_ROOT / "data" / "staging" / "_chunks" / uid).exists()
    _cleanup_batch(staged["batch_uuid"])


def test_chunked_stage_reports_missing_chunks_and_recovers():
    client = TestClient(app)
    atrl_bytes = open("/home/user/drive_mirror/Input folder/ATRL.txt", "rb").read()
    pieces = _chunk_payload(atrl_bytes, chunk_size=128)
    uid = "testchunk0002-xx"

    # Upload all pieces EXCEPT index 1
    for i, piece in enumerate(pieces):
        if i == 1:
            continue
        res = client.post(
            f"/api/imports/upload-chunk?upload_id={uid}&name=ATRL.txt&idx={i}&total={len(pieces)}",
            content=piece,
        )
        assert res.status_code == 200

    res2 = client.post(
        "/api/imports/stage-chunked",
        json={"uploads": [{"upload_id": uid, "name": "ATRL.txt", "total_chunks": len(pieces)}]},
    )
    assert res2.status_code == 409
    detail = res2.json()["detail"]
    assert detail["uploads"][0]["missing"] == [1]

    # Send the missing piece, retry -> full success
    client.post(
        f"/api/imports/upload-chunk?upload_id={uid}&name=ATRL.txt&idx=1&total={len(pieces)}",
        content=pieces[1],
    )
    res3 = client.post(
        "/api/imports/stage-chunked",
        json={"uploads": [{"upload_id": uid, "name": "ATRL.txt", "total_chunks": len(pieces)}]},
    )
    assert res3.status_code == 200
    assert res3.json()["duplicates_ignored"] == 5
    _cleanup_batch(res3.json()["batch_uuid"])


def test_upload_chunk_input_validation():
    client = TestClient(app)
    uid = "valid-chunk-id-01"
    assert client.post(f"/api/imports/upload-chunk?upload_id={uid}&name=x.txt&idx=0&total=1").status_code == 400  # empty body
    assert client.post(f"/api/imports/upload-chunk?upload_id=bad&id=&name=x.txt&idx=0&total=1", content=b"a").status_code == 400
    assert client.post(f"/api/imports/upload-chunk?upload_id={uid}&name=x.txt&idx=5&total=3", content=b"a").status_code == 400
