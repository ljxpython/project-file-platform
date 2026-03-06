from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import psycopg

from project_file_platform.common.errors import AppError


@dataclass(slots=True)
class UploadSession:
    upload_id: str
    project_id: str
    rel_dir: str
    filename: str
    total_size: int
    chunk_size: int
    created_at: datetime


class UploadSessionStore(Protocol):
    def create_schema(self) -> None: ...

    def create_session(self, *, upload_id: str, project_id: str, rel_dir: str, filename: str, total_size: int, chunk_size: int) -> None: ...

    def get_session(self, upload_id: str) -> UploadSession: ...

    def upsert_part(self, upload_id: str, part_number: int, size: int) -> None: ...

    def list_parts(self, upload_id: str) -> list[int]: ...

    def delete_session(self, upload_id: str) -> None: ...


class InMemoryUploadSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, UploadSession] = {}
        self._parts: dict[str, dict[int, int]] = {}

    def create_schema(self) -> None:
        return

    def create_session(self, *, upload_id: str, project_id: str, rel_dir: str, filename: str, total_size: int, chunk_size: int) -> None:
        self._sessions[upload_id] = UploadSession(
            upload_id=upload_id,
            project_id=project_id,
            rel_dir=rel_dir,
            filename=filename,
            total_size=total_size,
            chunk_size=chunk_size,
            created_at=datetime.now(UTC),
        )
        self._parts[upload_id] = {}

    def get_session(self, upload_id: str) -> UploadSession:
        session = self._sessions.get(upload_id)
        if not session:
            raise AppError("UPLOAD_SESSION_NOT_FOUND", "upload session does not exist", 404)
        return session

    def upsert_part(self, upload_id: str, part_number: int, size: int) -> None:
        self.get_session(upload_id)
        self._parts.setdefault(upload_id, {})[part_number] = size

    def list_parts(self, upload_id: str) -> list[int]:
        self.get_session(upload_id)
        return sorted(self._parts.get(upload_id, {}).keys())

    def delete_session(self, upload_id: str) -> None:
        self._sessions.pop(upload_id, None)
        self._parts.pop(upload_id, None)


class PostgresUploadSessionStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def create_schema(self) -> None:
        # PostgreSQL schema is managed by SQL migrations.
        return

    def create_session(self, *, upload_id: str, project_id: str, rel_dir: str, filename: str, total_size: int, chunk_size: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO upload_sessions (upload_id, project_id, rel_dir, filename, total_size, chunk_size)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (upload_id, project_id, rel_dir, filename, total_size, chunk_size),
                )
            conn.commit()

    def get_session(self, upload_id: str) -> UploadSession:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT upload_id, project_id, rel_dir, filename, total_size, chunk_size, created_at
                    FROM upload_sessions
                    WHERE upload_id = %s
                    """,
                    (upload_id,),
                )
                row = cur.fetchone()

        if not row:
            raise AppError("UPLOAD_SESSION_NOT_FOUND", "upload session does not exist", 404)

        return UploadSession(
            upload_id=row[0],
            project_id=row[1],
            rel_dir=row[2],
            filename=row[3],
            total_size=row[4],
            chunk_size=row[5],
            created_at=row[6],
        )

    def upsert_part(self, upload_id: str, part_number: int, size: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO upload_parts (upload_id, part_number, size)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (upload_id, part_number)
                    DO UPDATE SET size = EXCLUDED.size
                    """,
                    (upload_id, part_number, size),
                )
            conn.commit()

    def list_parts(self, upload_id: str) -> list[int]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT part_number
                    FROM upload_parts
                    WHERE upload_id = %s
                    ORDER BY part_number ASC
                    """,
                    (upload_id,),
                )
                rows = cur.fetchall()

        return [row[0] for row in rows]

    def delete_session(self, upload_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM upload_sessions WHERE upload_id = %s", (upload_id,))
            conn.commit()


def build_upload_store(dsn: str) -> UploadSessionStore:
    if dsn.strip().lower() == "memory://":
        return InMemoryUploadSessionStore()
    return PostgresUploadSessionStore(dsn)
