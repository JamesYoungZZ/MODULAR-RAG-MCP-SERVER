import pytest

from core import Chunk, ChunkRecord
from ingestion.embedding import BatchProcessor


class FakeDenseEncoder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode_chunks(self, chunks: list[Chunk], trace: object | None = None) -> list[ChunkRecord]:
        self.calls.append([chunk.id for chunk in chunks])
        return [
            ChunkRecord(
                id=chunk.id,
                text=chunk.text,
                metadata=dict(chunk.metadata),
                dense_vector=[float(index), float(len(chunk.text))],
            )
            for index, chunk in enumerate(chunks)
        ]


class FakeSparseEncoder:
    def __init__(self, id_suffix: str = "") -> None:
        self.id_suffix = id_suffix
        self.calls: list[list[str]] = []

    def encode_chunks(self, chunks: list[Chunk], trace: object | None = None) -> list[ChunkRecord]:
        self.calls.append([chunk.id for chunk in chunks])
        return [
            ChunkRecord(
                id=f"{chunk.id}{self.id_suffix}",
                text=chunk.text,
                metadata={**chunk.metadata, "sparse_doc_length": len(chunk.text.split())},
                sparse_vector={chunk.text.lower(): 1.0} if chunk.text else {},
            )
            for chunk in chunks
        ]


def test_batch_processor_splits_five_chunks_into_three_stable_batches() -> None:
    dense_encoder = FakeDenseEncoder()
    sparse_encoder = FakeSparseEncoder()
    chunks = [_chunk(index) for index in range(5)]
    clock = iter([1.0, 1.2, 2.0, 2.3, 3.0, 3.4])

    result = BatchProcessor(
        dense_encoder=dense_encoder,  # type: ignore[arg-type]
        sparse_encoder=sparse_encoder,  # type: ignore[arg-type]
        batch_size=2,
        clock=lambda: next(clock),
    ).process_chunks(chunks)

    assert dense_encoder.calls == [["chunk-0", "chunk-1"], ["chunk-2", "chunk-3"], ["chunk-4"]]
    assert sparse_encoder.calls == dense_encoder.calls
    assert [record.id for record in result.records] == ["chunk-0", "chunk-1", "chunk-2", "chunk-3", "chunk-4"]
    assert [metric.chunk_count for metric in result.batch_metrics] == [2, 2, 1]
    assert [(metric.start_index, metric.end_index) for metric in result.batch_metrics] == [(0, 2), (2, 4), (4, 5)]
    assert [metric.duration_seconds for metric in result.batch_metrics] == pytest.approx([0.2, 0.3, 0.4])


def test_batch_processor_merges_dense_and_sparse_records() -> None:
    result = BatchProcessor(
        dense_encoder=FakeDenseEncoder(),  # type: ignore[arg-type]
        sparse_encoder=FakeSparseEncoder(),  # type: ignore[arg-type]
        batch_size=10,
    ).process_chunks([_chunk(0, text="Alpha")])

    record = result.records[0]
    assert record.id == "chunk-0"
    assert record.text == "Alpha"
    assert record.dense_vector == [0.0, 5.0]
    assert record.sparse_vector == {"alpha": 1.0}
    assert record.metadata == {"source_path": "docs/a.pdf", "chunk_index": 0, "sparse_doc_length": 1}


def test_batch_processor_returns_empty_result_for_empty_input() -> None:
    result = BatchProcessor(
        dense_encoder=FakeDenseEncoder(),  # type: ignore[arg-type]
        sparse_encoder=FakeSparseEncoder(),  # type: ignore[arg-type]
    ).process_chunks([])

    assert result.records == []
    assert result.batch_metrics == []


def test_batch_processor_rejects_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size must be greater than zero"):
        BatchProcessor(dense_encoder=FakeDenseEncoder(), sparse_encoder=FakeSparseEncoder(), batch_size=0)  # type: ignore[arg-type]


def test_batch_processor_rejects_mismatched_record_ids() -> None:
    processor = BatchProcessor(
        dense_encoder=FakeDenseEncoder(),  # type: ignore[arg-type]
        sparse_encoder=FakeSparseEncoder(id_suffix="-wrong"),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="record ids must match"):
        processor.process_chunks([_chunk(0)])


def _chunk(index: int, text: str | None = None) -> Chunk:
    chunk_text = text if text is not None else f"Text {index}"
    return Chunk(
        id=f"chunk-{index}",
        text=chunk_text,
        metadata={"source_path": "docs/a.pdf", "chunk_index": index},
        start_offset=index * 10,
        end_offset=index * 10 + len(chunk_text),
        source_ref="doc-1",
    )