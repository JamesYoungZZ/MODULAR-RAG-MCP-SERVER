"""Ingestion pipeline orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import Chunk, ChunkRecord, Document
from core.settings import Settings
from ingestion.chunking import DocumentChunker
from ingestion.embedding import BatchProcessingResult, BatchProcessor
from ingestion.storage import BM25Indexer, ImageStorage, VectorUpserter
from ingestion.transform import BaseTransform
from libs.loader import BaseLoader, FileIntegrityChecker, PdfLoader, SQLiteIntegrityChecker


ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class IngestionResult:
    document: Document | None
    chunks: list[Chunk]
    records: list[ChunkRecord]
    skipped: bool
    file_hash: str
    vector_upsert_count: int
    bm25_upsert_count: int
    stored_images: list[dict[str, Any]]
    batch_metrics: list[Any]


class IngestionPipelineError(RuntimeError):
    """Raised when a named ingestion pipeline stage fails."""

    def __init__(self, stage: str, source_path: str | Path, cause: Exception) -> None:
        self.stage = stage
        self.source_path = str(source_path)
        super().__init__(f"Ingestion stage '{stage}' failed for {source_path}: {cause}")


class IngestionPipeline:
    """Run integrity, load, split, transform, encode, and storage stages."""

    def __init__(
        self,
        settings: Settings | None = None,
        integrity_checker: FileIntegrityChecker | None = None,
        loader: BaseLoader | None = None,
        chunker: DocumentChunker | None = None,
        transforms: Sequence[BaseTransform] | None = None,
        batch_processor: BatchProcessor | None = None,
        vector_upserter: VectorUpserter | None = None,
        bm25_indexer: BM25Indexer | None = None,
        image_storage: ImageStorage | None = None,
        collection: str = "default",
        on_progress: ProgressCallback | None = None,
    ) -> None:
        if settings is None and (chunker is None or batch_processor is None or vector_upserter is None):
            raise ValueError("settings are required unless chunker, batch_processor, and vector_upserter are injected")
        self.integrity_checker = integrity_checker or SQLiteIntegrityChecker()
        self.loader = loader or PdfLoader()
        self.chunker = chunker or DocumentChunker(settings)  # type: ignore[arg-type]
        self.transforms = list(transforms or [])
        self.batch_processor = batch_processor or BatchProcessor(settings=settings)
        self.vector_upserter = vector_upserter or VectorUpserter(settings=settings)
        self.bm25_indexer = bm25_indexer or BM25Indexer()
        self.image_storage = image_storage or ImageStorage()
        self.collection = collection
        self.on_progress = on_progress

    def ingest(self, source_path: str | Path, force: bool = False, trace: Any | None = None) -> IngestionResult:
        path = Path(source_path)
        file_hash = self._run_stage("integrity", path, lambda: self.integrity_checker.compute_sha256(path))
        if not force and self._run_stage("integrity", path, lambda: self.integrity_checker.should_skip(file_hash)):
            self._progress("skipped", {"source_path": str(path), "file_hash": file_hash})
            return IngestionResult(
                document=None,
                chunks=[],
                records=[],
                skipped=True,
                file_hash=file_hash,
                vector_upsert_count=0,
                bm25_upsert_count=0,
                stored_images=[],
                batch_metrics=[],
            )

        try:
            document = self._run_stage("load", path, lambda: self.loader.load(path))
            stored_images = self._run_stage("image_storage", path, lambda: self._store_document_images(document))
            chunks = self._run_stage("split", path, lambda: self.chunker.split_document(document))
            chunks = self._run_stage("transform", path, lambda: self._transform_chunks(chunks, trace=trace))
            batch_result = self._run_stage("encode", path, lambda: self.batch_processor.process_chunks(chunks, trace=trace))
            vector_count = self._run_stage("vector_upsert", path, lambda: self.vector_upserter.upsert_records(batch_result.records, trace=trace))
            bm25_count = self._run_stage("bm25_upsert", path, lambda: self._upsert_bm25(batch_result.records))
            self._run_stage("integrity", path, lambda: self.integrity_checker.mark_success(file_hash, path, chunk_count=len(chunks)))
        except IngestionPipelineError as exc:
            self.integrity_checker.mark_failed(file_hash, str(exc), path)
            raise

        self._progress("finished", {"source_path": str(path), "chunks": len(chunks), "records": len(batch_result.records)})
        return IngestionResult(
            document=document,
            chunks=chunks,
            records=batch_result.records,
            skipped=False,
            file_hash=file_hash,
            vector_upsert_count=vector_count,
            bm25_upsert_count=bm25_count,
            stored_images=stored_images,
            batch_metrics=list(batch_result.batch_metrics),
        )

    def _transform_chunks(self, chunks: list[Chunk], trace: Any | None = None) -> list[Chunk]:
        transformed_chunks = chunks
        for transform in self.transforms:
            transformed_chunks = transform.transform_chunks(transformed_chunks, trace=trace)
        return transformed_chunks

    def _store_document_images(self, document: Document) -> list[dict[str, Any]]:
        images = document.metadata.get("images", [])
        if not isinstance(images, list):
            return []
        stored_images: list[dict[str, Any]] = []
        doc_hash = str(document.metadata.get("file_hash", document.id))
        for image in images:
            if isinstance(image, dict):
                stored_images.append(self.image_storage.save_image_metadata(image, collection=self.collection, doc_hash=doc_hash))
        return stored_images

    def _upsert_bm25(self, records: Sequence[ChunkRecord]) -> int:
        count = self.bm25_indexer.upsert(records)
        self.bm25_indexer.save()
        return count

    def _run_stage(self, stage: str, source_path: Path, operation: Callable[[], Any]) -> Any:
        self._progress(stage, {"source_path": str(source_path), "status": "started"})
        try:
            result = operation()
        except IngestionPipelineError:
            raise
        except Exception as exc:
            self._progress(stage, {"source_path": str(source_path), "status": "failed", "error": str(exc)})
            raise IngestionPipelineError(stage, source_path, exc) from exc
        self._progress(stage, {"source_path": str(source_path), "status": "finished"})
        return result

    def _progress(self, stage: str, payload: dict[str, Any]) -> None:
        if self.on_progress is not None:
            self.on_progress(stage, payload)


__all__ = ["IngestionPipeline", "IngestionPipelineError", "IngestionResult", "ProgressCallback"]