from __future__ import annotations

import logging
import os
from pathlib import Path

import psycopg

from project_file_platform.common.config import get_config

logger = logging.getLogger("project_file_platform.migrations")

_SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _iter_migration_files(migrations_dir: Path) -> list[Path]:
    if not migrations_dir.exists() or not migrations_dir.is_dir():
        raise FileNotFoundError(f"migrations directory does not exist: {migrations_dir}")
    return sorted(path for path in migrations_dir.iterdir() if path.is_file() and path.suffix == ".sql")


def _version_from_name(file_name: str) -> str:
    return file_name.split("_", 1)[0]


def run_migrations(dsn: str, migrations_dir: Path) -> list[str]:
    if dsn.strip().lower() == "memory://":
        logger.info("skip migrations for memory dsn")
        return []

    files = _iter_migration_files(migrations_dir)
    if not files:
        logger.info("no migration files found: %s", migrations_dir)
        return []

    applied: list[str] = []

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_MIGRATIONS_SQL)
            cur.execute("SELECT version FROM schema_migrations")
            existing = {row[0] for row in cur.fetchall()}
        conn.commit()

        for migration_file in files:
            version = _version_from_name(migration_file.name)
            if version in existing:
                continue

            sql = migration_file.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    """
                    INSERT INTO schema_migrations (version, name)
                    VALUES (%s, %s)
                    """,
                    (version, migration_file.name),
                )
            conn.commit()
            applied.append(migration_file.name)
            existing.add(version)
            logger.info("applied migration: %s", migration_file.name)

    return applied


def resolve_migrations_dir() -> Path:
    env_value = os.getenv("APP_MIGRATIONS_DIR")
    if env_value:
        return Path(env_value).resolve()
    return Path("migrations").resolve()


def run_cli() -> None:
    config = get_config()
    migrations_dir = resolve_migrations_dir()
    applied = run_migrations(config.postgres.dsn, migrations_dir)

    if not applied:
        print(f"No migrations applied. directory={migrations_dir}")
        return

    print(f"Applied {len(applied)} migrations from {migrations_dir}:")
    for name in applied:
        print(f"- {name}")


if __name__ == "__main__":
    run_cli()
