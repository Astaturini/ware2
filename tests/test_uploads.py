from io import BytesIO
from pathlib import Path

from app import create_app


def test_upload_rejects_unsupported_file_type(tmp_path: Path) -> None:
    app = create_app(base_data_dir=tmp_path / "runs")
    response = app.test_client().post(
        "/api/decision/files",
        data={"file": (BytesIO(b"#!/bin/sh\necho unsafe"), "script.sh")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "CSV and JSON" in response.get_json()["error"]


def test_upload_rejects_overwrite(tmp_path: Path) -> None:
    app = create_app(base_data_dir=tmp_path / "runs")
    client = app.test_client()
    payload = {"file": (BytesIO(b"tick,task_type\n1,PICK\n"), "orders.csv")}

    assert client.post(
        "/api/decision/files",
        data=payload,
        content_type="multipart/form-data",
    ).status_code == 201

    response = client.post(
        "/api/decision/files",
        data={"file": (BytesIO(b"replacement"), "orders.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 409