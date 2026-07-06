from pathlib import Path

import pytest

from core import Chunk, ChunkRecord, Document
from ingestion import IngestionPipeline, IngestionPipelineError
from ingestion.embedding import BatchMetric, BatchProcessingResult
from ingestion.storage import BM25Indexer, ImageStorage
from ingestion.transform import BaseTransform


class FakeIntegrityChecker:
    def __init__(self, skip: bool = False) -> None:
        self.skip = skip
        self.successes: list[tuple[str, str, int | None]] = []
        self.failures: list[tuple[str, str]] = []

    def compute_sha256(self, path: str | Path) -> str:
        return "f" * 64

    def should_skip(self, file_hash: str) -> bool:
        return self.skip

    def mark_success(self, file_hash: str, file_path: str | Path, file_size: int | None = None, chunk_count: int | None = None) -> None:
        self.successes.append((file_hash, str(file_path), chunk_count))

    def mark_failed(self, file_hash: str, error_msg: str, file_path: str | Path | None = None, file_size: int | None = None) -> None:
        self.failures.append((file_hash, error_msg))


class FakeLoader:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path

    def load(self, path: str | Path) -> Document:
        return Document(
            id="doc-1",
            text="Alpha text\n[IMAGE: img-1]\nBeta text",
            metadata={
                "source_path": str(path),
                "doc_type": "pdf",
                "file_hash": "doc-hash",
                "images": [
                    {
                        "id": "img-1",
                        "path": str(self.image_path),
                        "page": 1,
                        "text_offset": 11,
                        "text_length": len("[IMAGE: img-1]"),
                        "position": {},
                    }
                ],
            },
        )


class FakeChunker:
    def split_document(self, document: Document) -> list[Chunk]:
        return [
            Chunk(
                id="chunk-1",
                text="Alpha text [IMAGE: img-1]",
                metadata={
                    "source_path": document.metadata["source_path"],
                    "chunk_index": 0,
                    "image_refs": ["img-1"],
                    "images": document.metadata["images"],
                },
                start_offset=0,
                end_offset=24,
                source_ref=document.id,
            ),
            Chunk(
                id="chunk-2",
                text="Beta text",
                metadata={"source_path": document.metadata["source_path"], "chunk_index": 1},
                start_offset=25,
                end_offset=34,
                source_ref=document.id,
            ),
        ]


class MarkingTransform(BaseTransform):
    def transform_chunk(self, chunk: Chunk, trace: object | None = None) -> Chunk:
        metadata = dict(chunk.metadata)
        metadata["transformed"] = True
        return Chunk(
            id=chunk.id,
            text=chunk.text,
            metadata=metadata,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            source_ref=chunk.source_ref,
        )


class FakeBatchProcessor:
    def process_chunks(self, chunks: list[Chunk], trace: object | None = None) -> BatchProcessingResult:
        return BatchProcessingResult(
            records=[
                ChunkRecord(
                    id=chunk.id,
                    text=chunk.text,
                    metadata={**chunk.metadata, "sparse_doc_length": len(chunk.text.split())},
                    dense_vector=[float(index), float(len(chunk.text))],
                    sparse_vector={chunk.text.split()[0].lower(): 1.0},
                )
                for index, chunk in enumerate(chunks)
            ],
            batch_metrics=[BatchMetric(batch_index=0, start_index=0, end_index=len(chunks), chunk_count=len(chunks), duration_seconds=0.1)],
        )


class FakeVectorUpserter:
    def __init__(self) -> None:
        self.records: list[ChunkRecord] = []

    def upsert_records(self, records: list[ChunkRecord], trace: object | None = None) -> int:
        self.records = list(records)
        return len(records)


def test_ingestion_pipeline_runs_full_mvp_flow(tmp_path) -> None:
    source_pdf = tmp_path / "sample.pdf"
    source_pdf.write_text("pdf bytes", encoding="utf-8")
    source_image = tmp_path / "source.png"
    source_image.write_bytes(b"image-bytes")
    integrity = FakeIntegrityChecker()
    vector_upserter = FakeVectorUpserter()
    progress_events: list[str] = []

    result = IngestionPipeline(
        integrity_checker=integrity,  # type: ignore[arg-type]
        loader=FakeLoader(source_image),  # type: ignore[arg-type]
        chunker=FakeChunker(),  # type: ignore[arg-type]
        transforms=[MarkingTransform()],
        batch_processor=FakeBatchProcessor(),  # type: ignore[arg-type]
        vector_upserter=vector_upserter,  # type: ignore[arg-type]
        bm25_indexer=BM25Indexer(tmp_path / "bm25"),
        image_storage=ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db"),
        collection="docs",
        on_progress=lambda stage, payload: progress_events.append(stage),
    ).ingest(source_pdf)

    assert result.skipped is False
    assert result.file_hash == "f" * 64
    assert [chunk.id for chunk in result.chunks] == ["chunk-1", "chunk-2"]
    assert all(chunk.metadata["transformed"] is True for chunk in result.chunks)
    assert result.vector_upsert_count == 2
    assert result.bm25_upsert_count == 2
    assert [record.id for record in vector_upserter.records] == ["chunk-1", "chunk-2"]
    assert (tmp_path / "bm25" / "index.json").exists()
    assert (tmp_path / "images" / "docs" / "img-1.png").read_bytes() == b"image-bytes"
    assert result.stored_images[0]["path"] == str(tmp_path / "images" / "docs" / "img-1.png")
    assert integrity.successes == [("f" * 64, str(source_pdf), 2)]
    assert "finished" in progress_events


def test_ingestion_pipeline_skips_successful_existing_file(tmp_path) -> None:
    source_pdf = tmp_path / "sample.pdf"
    source_pdf.write_text("pdf bytes", encoding="utf-8")
    integrity = FakeIntegrityChecker(skip=True)

    result = IngestionPipeline(
        integrity_checker=integrity,  # type: ignore[arg-type]
        loader=FakeLoader(tmp_path / "unused.png"),  # type: ignore[arg-type]
        chunker=FakeChunker(),  # type: ignore[arg-type]
        batch_processor=FakeBatchProcessor(),  # type: ignore[arg-type]
        vector_upserter=FakeVectorUpserter(),  # type: ignore[arg-type]
        bm25_indexer=BM25Indexer(tmp_path / "bm25"),
        image_storage=ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db"),
    ).ingest(source_pdf)

    assert result.skipped is True
    assert result.records == []
    assert integrity.successes == []


def test_ingestion_pipeline_wraps_failed_stage_and_marks_failed(tmp_path) -> None:
    source_pdf = tmp_path / "sample.pdf"
    source_pdf.write_text("pdf bytes", encoding="utf-8")
    integrity = FakeIntegrityChecker()

    class FailingLoader(FakeLoader):
        def load(self, path: str | Path) -> Document:
            raise RuntimeError("loader exploded")

    pipeline = IngestionPipeline(
        integrity_checker=integrity,  # type: ignore[arg-type]
        loader=FailingLoader(tmp_path / "unused.png"),  # type: ignore[arg-type]
        chunker=FakeChunker(),  # type: ignore[arg-type]
        batch_processor=FakeBatchProcessor(),  # type: ignore[arg-type]
        vector_upserter=FakeVectorUpserter(),  # type: ignore[arg-type]
        bm25_indexer=BM25Indexer(tmp_path / "bm25"),
        image_storage=ImageStorage(image_root=tmp_path / "images", db_path=tmp_path / "image_index.db"),
    )

    with pytest.raises(IngestionPipelineError, match="stage 'load' failed"):
        pipeline.ingest(source_pdf)

    assert integrity.failures
    assert "loader exploded" in integrity.failures[0][1]