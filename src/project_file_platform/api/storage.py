from __future__ import annotations

import os
import shutil
import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

from fastapi import UploadFile

from project_file_platform.api.path_utils import (
    normalize_filename,
    resolve_project_root,
    resolve_under_project,
)
from project_file_platform.api.upload_store import UploadSessionStore
from project_file_platform.common.config import AppConfig
from project_file_platform.common.errors import AppError


def _file_meta(project_root: Path, file_path: Path) -> dict[str, object]:
    stat = file_path.stat()
    rel = file_path.relative_to(project_root).as_posix()
    return {
        "name": file_path.name,
        "size": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        "path": rel,
    }


def list_projects(config: AppConfig) -> list[dict[str, str]]:
    return [{"project_id": project_id, "root_path": root_path} for project_id, root_path in sorted(config.projects.items())]


def list_files(
    *,
    config: AppConfig,
    project_id: str,
    path: str,
    keyword: str,
    page: int,
    page_size: int,
    sort_by: str,
    order: str,
) -> dict[str, object]:
    if page < 1:
        raise AppError("INVALID_PATH", "page must be >= 1", HTTPStatus.BAD_REQUEST)
    if page_size < 1 or page_size > 500:
        raise AppError("INVALID_PATH", "page_size must be within 1..500", HTTPStatus.BAD_REQUEST)

    root, directory, rel = resolve_under_project(project_id, path, config)
    if not directory.exists() or not directory.is_dir():
        raise AppError("FILE_NOT_FOUND", "directory does not exist", HTTPStatus.NOT_FOUND)

    entries: list[dict[str, object]] = []
    for child in directory.iterdir():
        if child.name == ".upload_sessions":
            continue
        if keyword and keyword.lower() not in child.name.lower():
            continue

        stat = child.stat()
        entries.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": None if child.is_dir() else stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                "path": child.relative_to(root).as_posix(),
            }
        )

    reverse = order.lower() != "asc"
    if sort_by == "name":
        entries.sort(key=lambda item: str(item["name"]).lower(), reverse=reverse)
    elif sort_by == "size":
        entries.sort(key=lambda item: int(item["size"] or 0), reverse=reverse)
    else:
        entries.sort(key=lambda item: str(item["updated_at"]), reverse=reverse)

    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "project_id": project_id,
        "path": rel,
        "keyword": keyword,
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": entries[start:end],
    }


def upload_file(*, config: AppConfig, project_id: str, directory: str, file: UploadFile) -> dict[str, object]:
    if not file.filename:
        raise AppError("INVALID_PATH", "filename is required", HTTPStatus.BAD_REQUEST)

    file_name = normalize_filename(file.filename)
    root, target_dir, _ = resolve_under_project(project_id, directory, config)
    target_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = config.max_file_size_bytes
    temp_path = target_dir / f".{uuid.uuid4().hex}.uploading"
    total = 0

    try:
        with temp_path.open("wb") as fh:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError("FILE_TOO_LARGE", "file exceeds max upload size", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                fh.write(chunk)

        final_path = target_dir / file_name
        os.replace(temp_path, final_path)
        return _file_meta(root, final_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def get_download_path(*, config: AppConfig, project_id: str, path: str) -> tuple[Path, Path]:
    root, target, _ = resolve_under_project(project_id, path, config)
    if not target.exists() or not target.is_file():
        raise AppError("FILE_NOT_FOUND", "file does not exist", HTTPStatus.NOT_FOUND)
    return root, target


def delete_path(*, config: AppConfig, project_id: str, path: str) -> dict[str, object]:
    root, target, rel = resolve_under_project(project_id, path, config)
    if target == root:
        raise AppError("INVALID_PATH", "project root cannot be deleted", HTTPStatus.BAD_REQUEST)
    if not target.exists():
        raise AppError("FILE_NOT_FOUND", "path does not exist", HTTPStatus.NOT_FOUND)

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return {"project_id": project_id, "path": rel, "deleted": True}


def _session_dir(project_root: Path, upload_id: str) -> Path:
    return project_root / ".upload_sessions" / upload_id


def init_chunk_upload(
    *,
    config: AppConfig,
    store: UploadSessionStore,
    project_id: str,
    path: str,
    filename: str,
    total_size: int,
    chunk_size: int,
) -> dict[str, object]:
    if total_size > config.max_file_size_bytes:
        raise AppError("FILE_TOO_LARGE", "file exceeds max upload size", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

    normalized_name = normalize_filename(filename)
    root, target_dir, rel_dir = resolve_under_project(project_id, path, config)
    target_dir.mkdir(parents=True, exist_ok=True)

    configured_chunk = config.chunk_size_bytes
    effective_chunk_size = min(chunk_size, configured_chunk) if chunk_size else configured_chunk

    upload_id = uuid.uuid4().hex
    session_dir = _session_dir(root, upload_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    store.create_session(
        upload_id=upload_id,
        project_id=project_id,
        rel_dir=rel_dir,
        filename=normalized_name,
        total_size=total_size,
        chunk_size=effective_chunk_size,
    )

    return {
        "upload_id": upload_id,
        "chunk_size": effective_chunk_size,
    }


def upload_chunk(*, config: AppConfig, store: UploadSessionStore, upload_id: str, part_number: int, file: UploadFile) -> dict[str, object]:
    if part_number < 1:
        raise AppError("INVALID_PATH", "part_number must be >= 1", HTTPStatus.BAD_REQUEST)

    session = store.get_session(upload_id)
    project_root = resolve_project_root(session.project_id, config)
    session_dir = _session_dir(project_root, upload_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    part_path = session_dir / f"part-{part_number:08d}.chunk"
    size = 0

    with part_path.open("wb") as fh:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > session.chunk_size:
                raise AppError("FILE_TOO_LARGE", "chunk exceeds configured chunk size", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            fh.write(chunk)

    store.upsert_part(upload_id, part_number, size)
    return {
        "upload_id": upload_id,
        "part_number": part_number,
        "size": size,
    }


def complete_chunk_upload(*, config: AppConfig, store: UploadSessionStore, upload_id: str, parts: list[int]) -> dict[str, object]:
    if not parts:
        raise AppError("UPLOAD_PART_MISSING", "parts list is required", HTTPStatus.BAD_REQUEST)

    session = store.get_session(upload_id)
    project_root = resolve_project_root(session.project_id, config)
    session_dir = _session_dir(project_root, upload_id)
    if not session_dir.exists():
        raise AppError("UPLOAD_SESSION_NOT_FOUND", "upload session temp files missing", HTTPStatus.NOT_FOUND)

    parts = sorted(set(parts))
    stored_parts = store.list_parts(upload_id)
    if parts != stored_parts:
        raise AppError("UPLOAD_PART_MISSING", "provided parts do not match uploaded parts", HTTPStatus.BAD_REQUEST)

    target_dir = (project_root / session.rel_dir).resolve() if session.rel_dir != "/" else project_root
    target_dir.mkdir(parents=True, exist_ok=True)
    final_path = target_dir / session.filename
    temp_path = target_dir / f".{upload_id}.assembling"

    written = 0
    try:
        with temp_path.open("wb") as out:
            for part_number in parts:
                part_path = session_dir / f"part-{part_number:08d}.chunk"
                if not part_path.exists():
                    raise AppError("UPLOAD_PART_MISSING", f"part {part_number} is missing", HTTPStatus.BAD_REQUEST)
                with part_path.open("rb") as fh:
                    shutil.copyfileobj(fh, out, length=1024 * 1024)
                written += part_path.stat().st_size

        if session.total_size and written != session.total_size:
            raise AppError("UPLOAD_PART_MISSING", "total assembled size does not match expected size", HTTPStatus.BAD_REQUEST)

        os.replace(temp_path, final_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    shutil.rmtree(session_dir, ignore_errors=True)
    store.delete_session(upload_id)

    return _file_meta(project_root, final_path)


def abort_chunk_upload(*, config: AppConfig, store: UploadSessionStore, upload_id: str) -> dict[str, object]:
    session = store.get_session(upload_id)
    project_root = resolve_project_root(session.project_id, config)
    session_dir = _session_dir(project_root, upload_id)
    shutil.rmtree(session_dir, ignore_errors=True)
    store.delete_session(upload_id)

    return {
        "upload_id": upload_id,
        "aborted": True,
    }
