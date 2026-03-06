from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    max_file_size_mb: int = Field(default=500, ge=1)
    chunk_size_mb: int = Field(default=8, ge=1)


class MCPConfig(BaseModel):
    max_inline_download_mb: int = Field(default=2, ge=1)


class PostgresConfig(BaseModel):
    dsn: str = "postgresql://fileplatform:fileplatform@postgres:5432/fileplatform"
    run_migrations_on_startup: bool = True


class ServiceConfig(BaseModel):
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_json: bool = True
    log_file_max_mb: int = Field(default=50, ge=1)
    log_backup_count: int = Field(default=10, ge=1)
    log_to_stdout: bool = True


class AppConfig(BaseModel):
    projects: dict[str, str]
    storage: StorageConfig = StorageConfig()
    mcp: MCPConfig = MCPConfig()
    postgres: PostgresConfig = PostgresConfig()
    service: ServiceConfig = ServiceConfig()

    @property
    def max_file_size_bytes(self) -> int:
        return self.storage.max_file_size_mb * 1024 * 1024

    @property
    def chunk_size_bytes(self) -> int:
        return self.storage.chunk_size_mb * 1024 * 1024

    @property
    def max_inline_download_bytes(self) -> int:
        return self.mcp.max_inline_download_mb * 1024 * 1024


DEFAULT_CONFIG_PATH = "config/app.toml"


def _load_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _apply_env_overrides(raw: dict) -> dict:
    raw.setdefault("storage", {})
    raw.setdefault("mcp", {})
    raw.setdefault("postgres", {})
    raw.setdefault("service", {})

    if value := os.getenv("APP_STORAGE_MAX_FILE_SIZE_MB"):
        raw["storage"]["max_file_size_mb"] = int(value)
    if value := os.getenv("APP_STORAGE_CHUNK_SIZE_MB"):
        raw["storage"]["chunk_size_mb"] = int(value)
    if value := os.getenv("APP_MCP_MAX_INLINE_DOWNLOAD_MB"):
        raw["mcp"]["max_inline_download_mb"] = int(value)
    if value := os.getenv("APP_POSTGRES_DSN"):
        raw["postgres"]["dsn"] = value
    if value := os.getenv("APP_POSTGRES_RUN_MIGRATIONS_ON_STARTUP"):
        raw["postgres"]["run_migrations_on_startup"] = value.lower() in {"1", "true", "yes", "on"}
    if value := os.getenv("APP_SERVICE_LOG_LEVEL"):
        raw["service"]["log_level"] = value
    if value := os.getenv("APP_SERVICE_LOG_DIR"):
        raw["service"]["log_dir"] = value
    if value := os.getenv("APP_SERVICE_LOG_JSON"):
        raw["service"]["log_json"] = value.lower() in {"1", "true", "yes", "on"}
    if value := os.getenv("APP_SERVICE_LOG_FILE_MAX_MB"):
        raw["service"]["log_file_max_mb"] = int(value)
    if value := os.getenv("APP_SERVICE_LOG_BACKUP_COUNT"):
        raw["service"]["log_backup_count"] = int(value)
    if value := os.getenv("APP_SERVICE_LOG_TO_STDOUT"):
        raw["service"]["log_to_stdout"] = value.lower() in {"1", "true", "yes", "on"}

    return raw


def _resolve_project_paths(projects: dict[str, str], *, cwd: Path) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for project_id, root in projects.items():
        root_path = Path(root)
        if not root_path.is_absolute():
            root_path = (cwd / root_path).resolve()
        else:
            root_path = root_path.resolve()
        resolved[project_id] = str(root_path)
    return resolved


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    config_path = Path(os.getenv("APP_CONFIG_PATH", DEFAULT_CONFIG_PATH)).resolve()
    raw = _load_toml(config_path)
    raw = _apply_env_overrides(raw)

    if "projects" not in raw or not raw["projects"]:
        raise ValueError("config `projects` is required")

    raw["projects"] = _resolve_project_paths(raw["projects"], cwd=Path.cwd())
    return AppConfig.model_validate(raw)


def clear_config_cache() -> None:
    get_config.cache_clear()
