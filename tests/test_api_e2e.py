from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from project_file_platform.common.config import clear_config_cache


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    projects_root = tmp_path / "storage" / "projects"
    project_a = projects_root / "project-a"
    project_b = projects_root / "project-b"
    project_a.mkdir(parents=True)
    project_b.mkdir(parents=True)

    config_path = tmp_path / "app.toml"
    config_path.write_text(
        "\n".join(
            [
                "[projects]",
                f'project-a = "{project_a}"',
                f'project-b = "{project_b}"',
                "",
                "[storage]",
                "max_file_size_mb = 2",
                "chunk_size_mb = 1",
                "",
                "[mcp]",
                "max_inline_download_mb = 1",
                "",
                "[postgres]",
                'dsn = "memory://"',
                "",
                "[service]",
                'log_level = "INFO"',
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("APP_POSTGRES_DSN", "memory://")

    clear_config_cache()
    from project_file_platform.api.main import app

    with TestClient(app) as test_client:
        yield test_client

    clear_config_cache()


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_list_projects(client: TestClient):
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert {item["project_id"] for item in items} == {"project-a", "project-b"}


def test_upload_download_roundtrip(client: TestClient):
    upload = client.post(
        "/api/v1/files/upload",
        data={"project_id": "project-a", "path": "/docs"},
        files={"file": ("hello.txt", b"hello world", "text/plain")},
    )
    assert upload.status_code == 200
    assert upload.json()["data"]["path"] == "docs/hello.txt"

    download = client.get(
        "/api/v1/files/download",
        params={"project_id": "project-a", "path": "docs/hello.txt"},
    )
    assert download.status_code == 200
    assert download.content == b"hello world"


def test_upload_overwrite(client: TestClient):
    for payload in (b"first", b"second"):
        resp = client.post(
            "/api/v1/files/upload",
            data={"project_id": "project-a", "path": "/"},
            files={"file": ("overwrite.txt", payload, "text/plain")},
        )
        assert resp.status_code == 200

    download = client.get(
        "/api/v1/files/download",
        params={"project_id": "project-a", "path": "overwrite.txt"},
    )
    assert download.content == b"second"


def test_path_traversal_blocked(client: TestClient):
    resp = client.get(
        "/api/v1/files",
        params={"project_id": "project-a", "path": "../outside"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PATH"


def test_cross_project_isolation(client: TestClient):
    client.post(
        "/api/v1/files/upload",
        data={"project_id": "project-a", "path": "/"},
        files={"file": ("isolated.txt", b"only-a", "text/plain")},
    )

    download = client.get(
        "/api/v1/files/download",
        params={"project_id": "project-b", "path": "isolated.txt"},
    )
    assert download.status_code == 404
    assert download.json()["error"]["code"] == "FILE_NOT_FOUND"


def test_list_pagination_and_keyword(client: TestClient):
    for name in ["a.log", "b.log", "c.txt"]:
        client.post(
            "/api/v1/files/upload",
            data={"project_id": "project-a", "path": "/logs"},
            files={"file": (name, b"x", "text/plain")},
        )

    resp = client.get(
        "/api/v1/files",
        params={
            "project_id": "project-a",
            "path": "/logs",
            "keyword": ".log",
            "page": 1,
            "page_size": 1,
            "sort_by": "name",
            "order": "asc",
        },
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "a.log"


def test_chunk_upload_complete(client: TestClient):
    init = client.post(
        "/api/v1/files/upload/init",
        json={
            "project_id": "project-a",
            "path": "/big",
            "filename": "data.bin",
            "total_size": 9,
            "chunk_size": 4,
        },
    )
    assert init.status_code == 200
    upload_id = init.json()["data"]["upload_id"]

    chunk1 = client.put(
        "/api/v1/files/upload/chunk",
        data={"upload_id": upload_id, "part_number": "1"},
        files={"chunk": ("part1", b"abc", "application/octet-stream")},
    )
    assert chunk1.status_code == 200

    chunk2 = client.put(
        "/api/v1/files/upload/chunk",
        data={"upload_id": upload_id, "part_number": "2"},
        files={"chunk": ("part2", b"def", "application/octet-stream")},
    )
    assert chunk2.status_code == 200

    chunk3 = client.put(
        "/api/v1/files/upload/chunk",
        data={"upload_id": upload_id, "part_number": "3"},
        files={"chunk": ("part3", b"ghi", "application/octet-stream")},
    )
    assert chunk3.status_code == 200

    complete = client.post(
        "/api/v1/files/upload/complete",
        json={"upload_id": upload_id, "parts": [1, 2, 3]},
    )
    assert complete.status_code == 200

    download = client.get(
        "/api/v1/files/download",
        params={"project_id": "project-a", "path": "big/data.bin"},
    )
    assert download.content == b"abcdefghi"


def test_chunk_missing_part(client: TestClient):
    init = client.post(
        "/api/v1/files/upload/init",
        json={
            "project_id": "project-a",
            "path": "/big",
            "filename": "broken.bin",
            "total_size": 6,
            "chunk_size": 4,
        },
    )
    upload_id = init.json()["data"]["upload_id"]

    client.put(
        "/api/v1/files/upload/chunk",
        data={"upload_id": upload_id, "part_number": "1"},
        files={"chunk": ("part1", b"abc", "application/octet-stream")},
    )

    complete = client.post(
        "/api/v1/files/upload/complete",
        json={"upload_id": upload_id, "parts": [1, 2]},
    )
    assert complete.status_code == 400
    assert complete.json()["error"]["code"] == "UPLOAD_PART_MISSING"


def test_file_too_large(client: TestClient):
    large_blob = b"x" * (3 * 1024 * 1024)
    resp = client.post(
        "/api/v1/files/upload",
        data={"project_id": "project-a", "path": "/"},
        files={"file": ("big.dat", large_blob, "application/octet-stream")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_delete_file_and_directory(client: TestClient):
    client.post(
        "/api/v1/files/upload",
        data={"project_id": "project-a", "path": "/del/me"},
        files={"file": ("gone.txt", b"bye", "text/plain")},
    )

    file_delete = client.delete(
        "/api/v1/files",
        params={"project_id": "project-a", "path": "del/me/gone.txt"},
    )
    assert file_delete.status_code == 200

    dir_delete = client.delete(
        "/api/v1/files",
        params={"project_id": "project-a", "path": "del"},
    )
    assert dir_delete.status_code == 200

    list_resp = client.get(
        "/api/v1/files",
        params={"project_id": "project-a", "path": "/"},
    )
    names = {item["name"] for item in list_resp.json()["data"]["items"]}
    assert "del" not in names
