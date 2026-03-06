from __future__ import annotations

import logging
import os
import time
import uuid
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from project_file_platform.api.models import (
    UploadAbortRequest,
    UploadCompleteRequest,
    UploadInitRequest,
)
from project_file_platform.api.migrations import resolve_migrations_dir, run_migrations
from project_file_platform.api.storage import (
    abort_chunk_upload,
    complete_chunk_upload,
    delete_path,
    get_download_path,
    init_chunk_upload,
    list_files,
    list_projects,
    upload_chunk,
    upload_file,
)
from project_file_platform.api.upload_store import UploadSessionStore, build_upload_store
from project_file_platform.common.config import AppConfig, get_config
from project_file_platform.common.errors import AppError
from project_file_platform.common.logging_utils import setup_logging
from project_file_platform.common.response import ok

logger = logging.getLogger("project_file_platform.api")


app = FastAPI(title="Project File Platform API", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    config = get_config()
    setup_logging("api", config.service)

    for root in config.projects.values():
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        (root_path / ".upload_sessions").mkdir(parents=True, exist_ok=True)
        try:
            root_path.chmod(0o777)
            (root_path / ".upload_sessions").chmod(0o777)
        except OSError:
            pass

    if config.postgres.run_migrations_on_startup:
        migrations_dir = resolve_migrations_dir()
        applied = run_migrations(config.postgres.dsn, migrations_dir)
        logger.info("migrations_dir=%s applied_count=%s", migrations_dir, len(applied))

    store = build_upload_store(config.postgres.dsn)
    store.create_schema()
    app.state.config = config
    app.state.upload_store = store


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    request.state.request_id = request_id
    started = time.monotonic()
    response = await call_next(request)
    cost_ms = int((time.monotonic() - started) * 1000)

    logger.info(
        "request_id=%s method=%s path=%s status=%s cost_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        cost_ms,
    )

    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.exception_handler(Exception)
async def internal_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error: %s", exc)
    payload = {
        "ok": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "internal server error",
        },
    }
    return JSONResponse(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, content=payload)


def _config(request: Request) -> AppConfig:
    return request.app.state.config


def _store(request: Request) -> UploadSessionStore:
    return request.app.state.upload_store


@app.get("/health")
def health() -> dict[str, object]:
    return ok({"status": "healthy"})


@app.get("/api/v1/projects")
def get_projects(request: Request) -> dict[str, object]:
    return ok({"items": list_projects(_config(request))})


@app.get("/api/v1/files")
def get_files(
    request: Request,
    project_id: str = Query(...),
    path: str = Query("/"),
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    sort_by: str = Query("updated_at"),
    order: str = Query("desc"),
) -> dict[str, object]:
    data = list_files(
        config=_config(request),
        project_id=project_id,
        path=path,
        keyword=keyword,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
    )
    return ok(data)


@app.post("/api/v1/files/upload")
def post_upload_file(
    request: Request,
    project_id: str = Form(...),
    path: str = Form("/"),
    file: UploadFile = File(...),
) -> dict[str, object]:
    data = upload_file(config=_config(request), project_id=project_id, directory=path, file=file)
    return ok(data)


@app.get("/api/v1/files/download")
def get_download_file(
    request: Request,
    project_id: str = Query(...),
    path: str = Query(...),
):
    _, target = get_download_path(config=_config(request), project_id=project_id, path=path)

    def iter_file():
        with target.open("rb") as fh:
            while chunk := fh.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


@app.delete("/api/v1/files")
def delete_file(
    request: Request,
    project_id: str = Query(...),
    path: str = Query(...),
) -> dict[str, object]:
    data = delete_path(config=_config(request), project_id=project_id, path=path)
    return ok(data)


@app.post("/api/v1/files/upload/init")
def post_upload_init(request: Request, payload: UploadInitRequest) -> dict[str, object]:
    data = init_chunk_upload(
        config=_config(request),
        store=_store(request),
        project_id=payload.project_id,
        path=payload.path,
        filename=payload.filename,
        total_size=payload.total_size,
        chunk_size=payload.chunk_size,
    )
    return ok(data)


@app.put("/api/v1/files/upload/chunk")
def put_upload_chunk(
    request: Request,
    upload_id: str = Form(...),
    part_number: int = Form(...),
    chunk: UploadFile = File(...),
) -> dict[str, object]:
    data = upload_chunk(
        config=_config(request),
        store=_store(request),
        upload_id=upload_id,
        part_number=part_number,
        file=chunk,
    )
    return ok(data)


@app.post("/api/v1/files/upload/complete")
def post_upload_complete(request: Request, payload: UploadCompleteRequest) -> dict[str, object]:
    data = complete_chunk_upload(
        config=_config(request),
        store=_store(request),
        upload_id=payload.upload_id,
        parts=payload.parts,
    )
    return ok(data)


@app.post("/api/v1/files/upload/abort")
def post_upload_abort(request: Request, payload: UploadAbortRequest) -> dict[str, object]:
    data = abort_chunk_upload(config=_config(request), store=_store(request), upload_id=payload.upload_id)
    return ok(data)


def run() -> None:
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("project_file_platform.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
