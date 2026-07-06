from pathlib import Path
import sys
from typing import Any

import pytest

from core import Chunk, ChunkRecord
from ingestion import IngestionResult

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import ingest


class FakePipeline:
    def __init__(self, skipped: bool = False) -> None:
        self.skipped = skipped
        self.calls: list[tuple[Path, bool]] = []

    def ingest(self, source_path: str | Path, force: bool = False) -> IngestionResult:
        path = Path(source_path)
        self.calls.append((path, force))
        chunks = [] if self.skipped else [_chunk(path.stem)]
        records = [] if self.skipped else [_record(path.stem)]
        return IngestionResult(
            document=None,
            chunks=chunks,
            records=records,
            skipped=self.skipped,
            file_hash="f" * 64,
            vector_upsert_count=0 if self.skipped else 1,
            bm25_upsert_count=0 if self.skipped else 1,
            stored_images=[],
            batch_metrics=[],
        )


def test_ingest_cli_runs_pipeline_for_single_pdf(tmp_path, capsys) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    pipeline = FakePipeline()
    created: list[tuple[object, str]] = []

    exit_code = ingest.main(
        ["--path", str(pdf_path), "--collection", "docs", "--force"],
        settings_loader=lambda path: object(),  # type: ignore[return-value]
        pipeline_factory=lambda settings, collection, on_progress: _factory(settings, collection, on_progress, pipeline, created),  # type: ignore[arg-type]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert created[0][1] == "docs"
    assert pipeline.calls == [(pdf_path, True)]
    assert "summary: files=1 ingested=1 skipped=0 chunks=1 vector_upserts=1 bm25_upserts=1" in output


def test_ingest_cli_discovers_directory_pdfs_in_stable_order(tmp_path) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "nested" / "b.pdf"
    ignored = tmp_path / "notes.md"
    second.parent.mkdir()
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")
    pipeline = FakePipeline()

    exit_code = ingest.main(
        ["--path", str(tmp_path)],
        settings_loader=lambda path: object(),  # type: ignore[return-value]
        pipeline_factory=lambda settings, collection, on_progress: pipeline,  # type: ignore[return-value]
    )

    assert exit_code == 0
    assert pipeline.calls == [(first, False), (second, False)]


def test_ingest_cli_reports_skipped_files(tmp_path, capsys) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")

    exit_code = ingest.main(
        ["--path", str(pdf_path)],
        settings_loader=lambda path: object(),  # type: ignore[return-value]
        pipeline_factory=lambda settings, collection, on_progress: FakePipeline(skipped=True),  # type: ignore[return-value]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "summary: files=1 ingested=0 skipped=1 chunks=0 vector_upserts=0 bm25_upserts=0" in output


def test_ingest_cli_returns_error_when_no_pdfs_found(tmp_path, capsys) -> None:
    (tmp_path / "notes.md").write_text("not a pdf", encoding="utf-8")

    exit_code = ingest.main(["--path", str(tmp_path)], settings_loader=lambda path: object())  # type: ignore[arg-type]

    assert exit_code == 1
    assert "No PDF files found" in capsys.readouterr().err


def test_ingest_cli_uses_settings_path(tmp_path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    seen_settings_paths: list[str] = []

    exit_code = ingest.main(
        ["--path", str(pdf_path), "--settings", "custom.yaml"],
        settings_loader=lambda path: _settings_loader(path, seen_settings_paths),  # type: ignore[arg-type]
        pipeline_factory=lambda settings, collection, on_progress: FakePipeline(),  # type: ignore[return-value]
    )

    assert exit_code == 0
    assert seen_settings_paths == ["custom.yaml"]


def test_ingest_cli_missing_path_exits_with_parser_error(tmp_path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        ingest.main(["--path", str(tmp_path / "missing.pdf")], settings_loader=lambda path: object())  # type: ignore[arg-type]

    assert exc_info.value.code == 2


def _factory(
    settings: object,
    collection: str,
    on_progress: Any,
    pipeline: FakePipeline,
    created: list[tuple[object, str]],
) -> FakePipeline:
    created.append((settings, collection))
    return pipeline


def _settings_loader(path: str | Path, seen_settings_paths: list[str]) -> object:
    seen_settings_paths.append(str(path))
    return object()


def _chunk(name: str) -> Chunk:
    return Chunk(id=f"chunk-{name}", text=name, metadata={"source_path": f"{name}.pdf", "chunk_index": 0})


def _record(name: str) -> ChunkRecord:
    return ChunkRecord(
        id=f"chunk-{name}",
        text=name,
        metadata={"source_path": f"{name}.pdf", "chunk_index": 0},
        dense_vector=[1.0],
        sparse_vector={name: 1.0},
    )