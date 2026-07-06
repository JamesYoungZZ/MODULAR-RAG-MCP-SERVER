"""File integrity tracking for incremental ingestion."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path


DEFAULT_INGESTION_HISTORY_DB = Path("data/db/ingestion_history.db")
_SQLITE_INIT_LOCK = threading.Lock()


class FileIntegrityChecker(ABC):
    """Abstract interface for detecting unchanged files before ingestion."""

    @abstractmethod
    def compute_sha256(self, path: str | Path) -> str:
        """Return the SHA256 hash for a file."""

    @abstractmethod
    def should_skip(self, file_hash: str) -> bool:
        """Return True when the file hash already has a successful ingestion record."""

    @abstractmethod
    def mark_success(self, file_hash: str, file_path: str | Path, file_size: int | None = None, chunk_count: int | None = None) -> None:
        """Record a successful ingestion for a file hash."""

    @abstractmethod
    def mark_failed(self, file_hash: str, error_msg: str, file_path: str | Path | None = None, file_size: int | None = None) -> None:
        """Record a failed ingestion attempt for a file hash."""


class SQLiteIntegrityChecker(FileIntegrityChecker):
    """SQLite-backed file integrity checker using ingestion_history records."""

    def __init__(self, db_path: str | Path = DEFAULT_INGESTION_HISTORY_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    def compute_sha256(self, path: str | Path) -> str:
        file_path = Path(path)
        digest = hashlib.sha256()
        with file_path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def should_skip(self, file_hash: str) -> bool:
        _validate_file_hash(file_hash)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM ingestion_history WHERE file_hash = ? AND status = 'success'",
                (file_hash,),
            ).fetchone()
        return row is not None

    def mark_success(self, file_hash: str, file_path: str | Path, file_size: int | None = None, chunk_count: int | None = None) -> None:
        _validate_file_hash(file_hash)
        stored_path = str(file_path)
        stored_size = _file_size(file_path) if file_size is None else file_size
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_history (file_hash, file_path, file_size, status, processed_at, error_msg, chunk_count)
                VALUES (?, ?, ?, 'success', CURRENT_TIMESTAMP, NULL, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    file_path = excluded.file_path,
                    file_size = excluded.file_size,
                    status = 'success',
                    processed_at = CURRENT_TIMESTAMP,
                    error_msg = NULL,
                    chunk_count = excluded.chunk_count
                """,
                (file_hash, stored_path, stored_size, chunk_count),
            )

    def mark_failed(self, file_hash: str, error_msg: str, file_path: str | Path | None = None, file_size: int | None = None) -> None:
        _validate_file_hash(file_hash)
        if not isinstance(error_msg, str) or not error_msg.strip():
            raise ValueError("error_msg must be a non-empty string")
        stored_path = str(file_path) if file_path is not None else ""
        stored_size = _file_size(file_path) if file_path is not None and file_size is None else file_size
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_history (file_hash, file_path, file_size, status, processed_at, error_msg, chunk_count)
                VALUES (?, ?, ?, 'failed', CURRENT_TIMESTAMP, ?, NULL)
                ON CONFLICT(file_hash) DO UPDATE SET
                    file_path = excluded.file_path,
                    file_size = excluded.file_size,
                    status = 'failed',
                    processed_at = CURRENT_TIMESTAMP,
                    error_msg = excluded.error_msg,
                    chunk_count = NULL
                """,
                (file_hash, stored_path, stored_size, error_msg),
            )

    def _initialize_db(self) -> None:
        with _SQLITE_INIT_LOCK:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ingestion_history (
                        file_hash TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        file_size INTEGER,
                        status TEXT NOT NULL CHECK(status IN ('success', 'failed', 'processing')),
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        error_msg TEXT,
                        chunk_count INTEGER
                    )
                    """
                )
                connection.execute("CREATE INDEX IF NOT EXISTS idx_status ON ingestion_history(status)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON ingestion_history(processed_at)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def _file_size(path: str | Path | None) -> int | None:
    if path is None:
        return None
    return Path(path).stat().st_size


def _validate_file_hash(file_hash: str) -> None:
    if not isinstance(file_hash, str) or not file_hash.strip():
        raise ValueError("file_hash must be a non-empty string")


__all__ = ["DEFAULT_INGESTION_HISTORY_DB", "FileIntegrityChecker", "SQLiteIntegrityChecker"]