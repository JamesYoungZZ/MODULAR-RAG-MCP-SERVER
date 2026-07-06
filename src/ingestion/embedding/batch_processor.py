"""Batch orchestration for ingestion embedding encoders."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from core import Chunk, ChunkRecord
from core.settings import Settings

from ingestion.embedding.dense_encoder import DenseEncoder
from ingestion.embedding.sparse_encoder import SparseEncoder


Clock = Callable[[], float]


@dataclass(frozen=True)
class BatchMetric:
    batch_index: int
    start_index: int
    end_index: int
    chunk_count: int
    duration_seconds: float


@dataclass(frozen=True)
class BatchProcessingResult:
    records: list[ChunkRecord]
    batch_metrics: list[BatchMetric]


class BatchProcessor:
    """Run dense and sparse encoders in stable chunk batches."""

    def __init__(
        self,
        settings: Settings | None = None,
        dense_encoder: DenseEncoder | None = None,
        sparse_encoder: SparseEncoder | None = None,
        batch_size: int = 32,
        clock: Clock = perf_counter,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")
        self.dense_encoder = dense_encoder or DenseEncoder(settings=settings)
        self.sparse_encoder = sparse_encoder or SparseEncoder()
        self.batch_size = batch_size
        self.clock = clock

    def process_chunks(self, chunks: Sequence[Chunk], trace: Any | None = None) -> BatchProcessingResult:
        chunk_list = list(chunks)
        records: list[ChunkRecord] = []
        batch_metrics: list[BatchMetric] = []

        for batch_index, start_index in enumerate(range(0, len(chunk_list), self.batch_size)):
            batch = chunk_list[start_index : start_index + self.batch_size]
            started_at = self.clock()
            dense_records = self.dense_encoder.encode_chunks(batch, trace=trace)
            sparse_records = self.sparse_encoder.encode_chunks(batch, trace=trace)
            records.extend(_merge_records(dense_records, sparse_records))
            finished_at = self.clock()
            batch_metrics.append(
                BatchMetric(
                    batch_index=batch_index,
                    start_index=start_index,
                    end_index=start_index + len(batch),
                    chunk_count=len(batch),
                    duration_seconds=max(0.0, finished_at - started_at),
                )
            )

        return BatchProcessingResult(records=records, batch_metrics=batch_metrics)


def _merge_records(dense_records: Sequence[ChunkRecord], sparse_records: Sequence[ChunkRecord]) -> list[ChunkRecord]:
    if len(dense_records) != len(sparse_records):
        raise ValueError("dense and sparse encoders must return the same number of records")

    merged_records: list[ChunkRecord] = []
    for dense_record, sparse_record in zip(dense_records, sparse_records, strict=True):
        if dense_record.id != sparse_record.id:
            raise ValueError("dense and sparse encoder record ids must match")
        metadata = dict(dense_record.metadata)
        metadata.update(sparse_record.metadata)
        merged_records.append(
            ChunkRecord(
                id=dense_record.id,
                text=dense_record.text,
                metadata=metadata,
                dense_vector=dense_record.dense_vector,
                sparse_vector=sparse_record.sparse_vector,
            )
        )
    return merged_records


__all__ = ["BatchMetric", "BatchProcessingResult", "BatchProcessor"]