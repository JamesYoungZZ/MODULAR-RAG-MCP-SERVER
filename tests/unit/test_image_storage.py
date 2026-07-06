import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ingestion.storage import ImageStorage


def test_image_storage_saves_file_and_returns_lookup_path(tmp_path) -> None:
    source_image = _write_image(tmp_path / "source.png", b"png-bytes")
    storage = ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db")

    saved_path = storage.save_image("img-1", source_image, collection="docs", doc_hash="doc-hash", page_num=2)

    assert saved_path == tmp_path / "images" / "docs" / "img-1.png"
    assert saved_path.read_bytes() == b"png-bytes"
    assert storage.get_path("img-1") == saved_path


def test_image_storage_creates_schema_and_wal_mode(tmp_path) -> None:
    db_path = tmp_path / "nested" / "image_index.db"

    ImageStorage(image_root=tmp_path / "images", db_path=db_path)

    with sqlite3.connect(db_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(image_index)").fetchall()]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert db_path.exists()
    assert columns == ["image_id", "file_path", "collection", "doc_hash", "page_num", "created_at"]
    assert journal_mode == "wal"


def test_image_storage_persists_mapping_across_instances(tmp_path) -> None:
    db_path = tmp_path / "image_index.db"
    image_root = tmp_path / "images"
    source_image = _write_image(tmp_path / "source.jpg", b"jpg-bytes")

    first_storage = ImageStorage(image_root=image_root, db_path=db_path)
    saved_path = first_storage.save_image("img-1", source_image, collection="docs")

    second_storage = ImageStorage(image_root=image_root, db_path=db_path)

    assert second_storage.get_path("img-1") == saved_path


def test_image_storage_lists_by_collection(tmp_path) -> None:
    storage = ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db")
    storage.save_image("img-b", _write_image(tmp_path / "b.png", b"b"), collection="docs", doc_hash="doc-1", page_num=2)
    storage.save_image("img-a", _write_image(tmp_path / "a.png", b"a"), collection="docs", doc_hash="doc-1", page_num=1)
    storage.save_image("img-c", _write_image(tmp_path / "c.png", b"c"), collection="notes")

    rows = storage.list_by_collection("docs")

    assert [row["image_id"] for row in rows] == ["img-a", "img-b"]
    assert [row["collection"] for row in rows] == ["docs", "docs"]
    assert rows[0]["doc_hash"] == "doc-1"
    assert rows[0]["page_num"] == 1


def test_image_storage_save_image_metadata_updates_path(tmp_path) -> None:
    source_image = _write_image(tmp_path / "source.png", b"png-bytes")
    storage = ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db")
    image = {"id": "img-1", "path": str(source_image), "page": 3, "text_offset": 0, "text_length": 12}

    stored_image = storage.save_image_metadata(image, collection="docs", doc_hash="doc-hash")

    assert stored_image["path"] == str(tmp_path / "images" / "docs" / "img-1.png")
    assert image["path"] == str(source_image)
    assert storage.get_path("img-1") == Path(stored_image["path"])


def test_image_storage_upsert_replaces_existing_mapping(tmp_path) -> None:
    storage = ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db")
    first_source = _write_image(tmp_path / "first.png", b"first")
    second_source = _write_image(tmp_path / "second.jpg", b"second")

    storage.save_image("img-1", first_source, collection="docs")
    updated_path = storage.save_image("img-1", second_source, collection="notes", doc_hash="doc-2")

    assert storage.get_path("img-1") == updated_path
    assert updated_path == tmp_path / "images" / "notes" / "img-1.jpg"
    assert storage.list_by_collection("docs") == []
    assert storage.list_by_collection("notes")[0]["doc_hash"] == "doc-2"


def test_image_storage_rejects_invalid_input(tmp_path) -> None:
    storage = ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db")

    with pytest.raises(ValueError, match="image_id must be a non-empty string"):
        storage.save_image(" ", tmp_path / "missing.png")
    with pytest.raises(FileNotFoundError, match="image source not found"):
        storage.save_image("img-1", tmp_path / "missing.png")
    with pytest.raises(ValueError, match="page_num must be a positive integer"):
        storage.save_image("img-1", _write_image(tmp_path / "source.png", b"x"), page_num=0)


def test_image_storage_supports_concurrent_writes(tmp_path) -> None:
    db_path = tmp_path / "image_index.db"
    image_root = tmp_path / "images"

    def save(index: int) -> None:
        source_image = _write_image(tmp_path / f"source-{index}.png", f"image-{index}".encode())
        ImageStorage(image_root=image_root, db_path=db_path).save_image(f"img-{index}", source_image, collection="docs")

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(save, range(8)))

    storage = ImageStorage(image_root=image_root, db_path=db_path)

    assert len(storage.list_by_collection("docs")) == 8


def _write_image(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path