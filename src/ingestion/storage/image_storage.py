"""Local image file storage with a SQLite image index."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Any


DEFAULT_IMAGE_ROOT = Path("data/images")
DEFAULT_IMAGE_INDEX_DB = Path("data/db/image_index.db")
_SQLITE_INIT_LOCK = threading.Lock()


class ImageStorage:
    """Save extracted images and persist image_id -> path mappings."""

    def __init__(
        self,
        image_root: str | Path = DEFAULT_IMAGE_ROOT,
        db_path: str | Path = DEFAULT_IMAGE_INDEX_DB,
    ) -> None:
        self.image_root = Path(image_root)
        self.db_path = Path(db_path)
        self.image_root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    def save_image(
        self,
        image_id: str,
        source_path: str | Path,
        collection: str = "default",
        doc_hash: str | None = None,
        page_num: int | None = None,
    ) -> Path:
        _validate_non_empty_string(image_id, "image_id")
        _validate_non_empty_string(collection, "collection")
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"image source not found: {source}")
        if page_num is not None and (not isinstance(page_num, int) or page_num < 1):
            raise ValueError("page_num must be a positive integer")

        target_path = self._target_path(image_id, source, collection)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target_path)
        self._upsert_index(image_id, target_path, collection, doc_hash, page_num)
        return target_path

    def save_image_metadata(self, image: dict[str, Any], collection: str = "default", doc_hash: str | None = None) -> dict[str, Any]:
        image_id = image.get("id")
        source_path = image.get("path")
        if not isinstance(image_id, str) or not image_id.strip():
            raise ValueError("image.id must be a non-empty string")
        if not isinstance(source_path, str) or not source_path.strip():
            raise ValueError("image.path must be a non-empty string")
        page = image.get("page")
        page_num = page if isinstance(page, int) else None
        saved_path = self.save_image(image_id, source_path, collection=collection, doc_hash=doc_hash, page_num=page_num)
        stored_image = dict(image)
        stored_image["path"] = str(saved_path)
        return stored_image

    def get_path(self, image_id: str) -> Path | None:
        _validate_non_empty_string(image_id, "image_id")
        with self._connect() as connection:
            row = connection.execute("SELECT file_path FROM image_index WHERE image_id = ?", (image_id,)).fetchone()
        return Path(row[0]) if row is not None else None

    def list_by_collection(self, collection: str) -> list[dict[str, Any]]:
        _validate_non_empty_string(collection, "collection")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT image_id, file_path, collection, doc_hash, page_num, created_at
                FROM image_index
                WHERE collection = ?
                ORDER BY image_id
                """,
                (collection,),
            ).fetchall()
        return [_row_to_mapping(row) for row in rows]

    def _target_path(self, image_id: str, source_path: Path, collection: str) -> Path:
        suffix = source_path.suffix or ".img"
        return self.image_root / collection / f"{image_id}{suffix}"

    def _upsert_index(
        self,
        image_id: str,
        file_path: Path,
        collection: str,
        doc_hash: str | None,
        page_num: int | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO image_index (image_id, file_path, collection, doc_hash, page_num, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(image_id) DO UPDATE SET
                    file_path = excluded.file_path,
                    collection = excluded.collection,
                    doc_hash = excluded.doc_hash,
                    page_num = excluded.page_num,
                    created_at = CURRENT_TIMESTAMP
                """,
                (image_id, str(file_path), collection, doc_hash, page_num),
            )

    def _initialize_db(self) -> None:
        with _SQLITE_INIT_LOCK:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS image_index (
                        image_id TEXT PRIMARY KEY,
                        file_path TEXT NOT NULL,
                        collection TEXT,
                        doc_hash TEXT,
                        page_num INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute("CREATE INDEX IF NOT EXISTS idx_collection ON image_index(collection)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON image_index(doc_hash)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def _row_to_mapping(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "image_id": row[0],
        "file_path": row[1],
        "collection": row[2],
        "doc_hash": row[3],
        "page_num": row[4],
        "created_at": row[5],
    }


def _validate_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


__all__ = ["DEFAULT_IMAGE_INDEX_DB", "DEFAULT_IMAGE_ROOT", "ImageStorage"]