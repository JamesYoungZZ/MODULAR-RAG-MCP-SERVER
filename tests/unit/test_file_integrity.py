import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from libs.loader import SQLiteIntegrityChecker


def test_compute_sha256_is_stable_for_same_file(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("hello integrity", encoding="utf-8")
    checker = SQLiteIntegrityChecker(tmp_path / "ingestion_history.db")

    first_hash = checker.compute_sha256(source_file)
    second_hash = checker.compute_sha256(source_file)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_mark_success_makes_file_hash_skippable(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("hello integrity", encoding="utf-8")
    checker = SQLiteIntegrityChecker(tmp_path / "ingestion_history.db")
    file_hash = checker.compute_sha256(source_file)

    assert checker.should_skip(file_hash) is False

    checker.mark_success(file_hash, source_file, chunk_count=3)

    assert checker.should_skip(file_hash) is True


def test_database_file_and_schema_are_created(tmp_path) -> None:
    db_path = tmp_path / "nested" / "ingestion_history.db"

    SQLiteIntegrityChecker(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(ingestion_history)").fetchall()]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert db_path.exists()
    assert columns == ["file_hash", "file_path", "file_size", "status", "processed_at", "error_msg", "chunk_count"]
    assert journal_mode == "wal"


def test_mark_failed_does_not_make_file_hash_skippable(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("hello integrity", encoding="utf-8")
    checker = SQLiteIntegrityChecker(tmp_path / "ingestion_history.db")
    file_hash = checker.compute_sha256(source_file)

    checker.mark_failed(file_hash, "parse failed", source_file)

    assert checker.should_skip(file_hash) is False


def test_mark_success_replaces_previous_failed_record(tmp_path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("hello integrity", encoding="utf-8")
    checker = SQLiteIntegrityChecker(tmp_path / "ingestion_history.db")
    file_hash = checker.compute_sha256(source_file)

    checker.mark_failed(file_hash, "parse failed", source_file)
    checker.mark_success(file_hash, source_file, chunk_count=2)

    with sqlite3.connect(checker.db_path) as connection:
        status, error_msg, chunk_count = connection.execute(
            "SELECT status, error_msg, chunk_count FROM ingestion_history WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()

    assert status == "success"
    assert error_msg is None
    assert chunk_count == 2


def test_concurrent_success_writes_are_supported(tmp_path) -> None:
    db_path = tmp_path / "ingestion_history.db"

    def write_record(index: int) -> None:
        source_file = tmp_path / f"sample-{index}.md"
        source_file.write_text(f"content {index}", encoding="utf-8")
        checker = SQLiteIntegrityChecker(db_path)
        checker.mark_success(checker.compute_sha256(source_file), source_file, chunk_count=index)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write_record, range(8)))

    with sqlite3.connect(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM ingestion_history WHERE status = 'success'").fetchone()[0]

    assert count == 8


def test_empty_file_hash_is_rejected(tmp_path) -> None:
    checker = SQLiteIntegrityChecker(tmp_path / "ingestion_history.db")

    with pytest.raises(ValueError, match="file_hash must be a non-empty string"):
        checker.should_skip(" ")