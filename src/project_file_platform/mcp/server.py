from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import httpx
from fastmcp import FastMCP

from project_file_platform.common.config import get_config
from project_file_platform.common.logging_utils import setup_logging


@dataclass(slots=True)
class APIClient:
    base_url: str
    timeout: float = 60.0

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _handle_error(self, response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except Exception:
            return {
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": response.text,
                },
            }

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self._url(path), params=params)
        if resp.status_code >= 400:
            return self._handle_error(resp)
        return resp.json()

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self._url(path), json=payload)
        if resp.status_code >= 400:
            return self._handle_error(resp)
        return resp.json()

    def post_multipart(self, path: str, *, data: dict[str, Any], files: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self._url(path), data=data, files=files)
        if resp.status_code >= 400:
            return self._handle_error(resp)
        return resp.json()

    def put_multipart(self, path: str, *, data: dict[str, Any], files: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.put(self._url(path), data=data, files=files)
        if resp.status_code >= 400:
            return self._handle_error(resp)
        return resp.json()


config = get_config()
api = APIClient(base_url=os.getenv("API_BASE_URL", "http://api:8000"))
mcp = FastMCP("project-file-platform-mcp")


def _split_target_path(path: str) -> tuple[str, str]:
    p = PurePosixPath(path.replace("\\", "/"))
    name = p.name
    if not name:
        raise ValueError("path must include filename")
    parent = p.parent.as_posix()
    if parent in {"", "."}:
        parent = "/"
    return parent, name


@mcp.tool
def list_projects() -> dict[str, Any]:
    return api.get("/api/v1/projects")


@mcp.tool
def list_files(
    project_id: str,
    path: str = "/",
    keyword: str = "",
    page: int = 1,
    page_size: int = 100,
    sort_by: str = "updated_at",
    order: str = "desc",
) -> dict[str, Any]:
    return api.get(
        "/api/v1/files",
        params={
            "project_id": project_id,
            "path": path,
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "order": order,
        },
    )


@mcp.tool
def upload_file(project_id: str, path: str, content_base64: str) -> dict[str, Any]:
    directory, filename = _split_target_path(path)
    content = base64.b64decode(content_base64)

    return api.post_multipart(
        "/api/v1/files/upload",
        data={"project_id": project_id, "path": directory},
        files={"file": (filename, content, "application/octet-stream")},
    )


@mcp.tool
def upload_file_chunked(project_id: str, path: str, filename: str, chunks_base64: list[str]) -> dict[str, Any]:
    chunks = [base64.b64decode(item) for item in chunks_base64]
    total_size = sum(len(chunk) for chunk in chunks)
    chunk_size = max((len(chunk) for chunk in chunks), default=config.chunk_size_bytes)

    init_resp = api.post_json(
        "/api/v1/files/upload/init",
        {
            "project_id": project_id,
            "path": path,
            "filename": filename,
            "total_size": total_size,
            "chunk_size": chunk_size,
        },
    )
    if not init_resp.get("ok"):
        return init_resp

    upload_id = init_resp["data"]["upload_id"]
    uploaded_parts: list[int] = []

    try:
        for index, chunk in enumerate(chunks, start=1):
            chunk_resp = api.put_multipart(
                "/api/v1/files/upload/chunk",
                data={"upload_id": upload_id, "part_number": str(index)},
                files={"chunk": (f"part-{index}.chunk", chunk, "application/octet-stream")},
            )
            if not chunk_resp.get("ok"):
                return chunk_resp
            uploaded_parts.append(index)

        return api.post_json(
            "/api/v1/files/upload/complete",
            {
                "upload_id": upload_id,
                "parts": uploaded_parts,
            },
        )
    except Exception:
        api.post_json("/api/v1/files/upload/abort", {"upload_id": upload_id})
        raise


@mcp.tool
def download_file(project_id: str, path: str) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            api._url("/api/v1/files/download"),
            params={"project_id": project_id, "path": path},
        )

    if response.status_code >= 400:
        return api._handle_error(response)

    content = response.content
    if len(content) > config.max_inline_download_bytes:
        return {
            "ok": False,
            "error": {
                "code": "MCP_PAYLOAD_TOO_LARGE",
                "message": "file is too large for inline MCP response",
            },
        }

    return {
        "ok": True,
        "data": {
            "path": path,
            "size": len(content),
            "content_base64": base64.b64encode(content).decode("utf-8"),
        },
    }


@mcp.tool
def delete_file(project_id: str, path: str) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        response = client.delete(
            api._url("/api/v1/files"),
            params={"project_id": project_id, "path": path},
        )

    if response.status_code >= 400:
        return api._handle_error(response)
    return response.json()


def run() -> None:
    setup_logging("mcp", config.service)
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport in {"http", "sse", "streamable-http"}:
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8001"))
        mcp.run(transport=transport, host=host, port=port)
        return
    mcp.run(transport=transport)


if __name__ == "__main__":
    run()
