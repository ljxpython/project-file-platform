from __future__ import annotations

from http import HTTPStatus
from pathlib import Path, PurePosixPath

from project_file_platform.common.config import AppConfig
from project_file_platform.common.errors import AppError


def _validate_path_part(part: str) -> None:
    if part in {"", ".", ".."}:
        raise AppError("INVALID_PATH", "invalid path segment", HTTPStatus.BAD_REQUEST)
    if any(ord(ch) < 32 for ch in part):
        raise AppError("INVALID_PATH", "path contains control character", HTTPStatus.BAD_REQUEST)


def normalize_relative_path(path: str | None) -> PurePosixPath:
    raw = (path or "").strip().replace("\\", "/")
    if raw in {"", "/", "."}:
        return PurePosixPath(".")

    # API accepts "/dir/sub" style input, but it is always resolved as project-internal relative path.
    raw = raw.lstrip("/")
    posix = PurePosixPath(raw)

    parts: list[str] = []
    for part in posix.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise AppError("INVALID_PATH", "path traversal is not allowed", HTTPStatus.BAD_REQUEST)
        _validate_path_part(part)
        parts.append(part)

    return PurePosixPath(*parts) if parts else PurePosixPath(".")


def normalize_filename(filename: str) -> str:
    trimmed = filename.strip()
    if not trimmed:
        raise AppError("INVALID_PATH", "filename is required", HTTPStatus.BAD_REQUEST)
    if "/" in trimmed or "\\" in trimmed:
        raise AppError("INVALID_PATH", "filename must not contain path separators", HTTPStatus.BAD_REQUEST)
    _validate_path_part(trimmed)
    return trimmed


def resolve_project_root(project_id: str, config: AppConfig) -> Path:
    if project_id not in config.projects:
        raise AppError("INVALID_PROJECT", f"project `{project_id}` is not configured", HTTPStatus.BAD_REQUEST)
    return Path(config.projects[project_id]).resolve()


def resolve_under_project(project_id: str, rel_path: str | None, config: AppConfig) -> tuple[Path, Path, str]:
    root = resolve_project_root(project_id, config)
    normalized = normalize_relative_path(rel_path)
    candidate = (root / normalized).resolve()

    if candidate != root and root not in candidate.parents:
        raise AppError("INVALID_PATH", "resolved path is outside project root", HTTPStatus.BAD_REQUEST)

    rel = "/" if normalized == PurePosixPath(".") else normalized.as_posix()
    return root, candidate, rel
