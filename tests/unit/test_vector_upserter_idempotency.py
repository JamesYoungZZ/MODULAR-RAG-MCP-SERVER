from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from core import ChunkRecord
from ingestion.storage import VectorUpserter, stable_chunk_id
from libs.vector_store import BaseVectorStore


class FakeVectorStore(BaseVectorStore):
    def __init__(self) -> None:
        self.calls: list[list[Mapping[str, Any]]] = []
        self.records_by_id: dict[str, Mapping[str, Any]] = {}

    def upsert(self, records: Sequence[Mapping[str, Any]], trace: object | None = None) -> int:
        self.calls.append(list(records))
        for record in records:
            self.records_by_id[str(record["id"])] = record
        return len(records)

    def query(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
        trace: object | None = None,
    ) -> list[Mapping[str, Any]]:
        return []


def test_vector_upserter_generates_same_id_for_same_chunk_content() -> None:
    vector_store = FakeVectorStore()
    upserter = VectorUpserter(vector_store=vector_store)
    record = _record("chunk-original", "Alpha text", chunk_index=3)

    first_written = upserter.upsert_records([record])
    second_written = upserter.upsert_records([record])

    first_id = vector_store.calls[0][0]["id"]
    second_id = vector_store.calls[1][0]["id"]
    assert first_written == 1
    assert second_written == 1
    assert first_id == second_id
    assert len(vector_store.records_by_id) == 1
    assert vector_store.records_by_id[str(first_id)]["metadata"]["original_chunk_id"] == "chunk-original"


def test_vector_upserter_changes_id_when_content_changes() -> None:
    original = _record("chunk-original", "Alpha text", chunk_index=3)
    changed = _record("chunk-original", "Alpha text changed", chunk_index=3)

    assert stable_chunk_id(original) != stable_chunk_id(changed)


def test_vector_upserter_supports_batch_upsert_and_preserves_order() -> None:
    vector_store = FakeVectorStore()
    records = [_record("chunk-1", "Alpha", chunk_index=0), _record("chunk-2", "Beta", chunk_index=1)]

    written = VectorUpserter(vector_store=vector_store).upsert_records(records)

    assert written == 2
    upserted = vector_store.calls[0]
    assert [record["text"] for record in upserted] == ["Alpha", "Beta"]
    assert [record["vector"] for record in upserted] == [[0.1, 0.2], [0.1, 0.2]]
    assert [record["metadata"]["original_chunk_id"] for record in upserted] == ["chunk-1", "chunk-2"]


def test_vector_upserter_keeps_source_metadata_and_content_hash() -> None:
    vector_record = VectorUpserter(vector_store=FakeVectorStore()).to_vector_record(_record("chunk-1", "Alpha"))

    assert vector_record["metadata"]["source_path"] == "docs/a.pdf"
    assert vector_record["metadata"]["chunk_index"] == 0
    assert len(vector_record["metadata"]["content_hash"]) == 64


def test_vector_upserter_rejects_records_without_dense_vector() -> None:
    upserter = VectorUpserter(vector_store=FakeVectorStore())
    record = ChunkRecord(id="chunk-1", text="Alpha", metadata={"source_path": "docs/a.pdf", "chunk_index": 0})

    with pytest.raises(ValueError, match="dense_vector is required"):
        upserter.upsert_records([record])


def test_vector_upserter_requires_chunk_index_metadata() -> None:
    record = ChunkRecord(
        id="chunk-1",
        text="Alpha",
        metadata={"source_path": "docs/a.pdf"},
        dense_vector=[0.1, 0.2],
    )

    with pytest.raises(ValueError, match="metadata.chunk_index"):
        stable_chunk_id(record)


def test_vector_upserter_requires_settings_or_vector_store() -> None:
    with pytest.raises(ValueError, match="requires either settings or a vector store client"):
        VectorUpserter()


def _record(chunk_id: str, text: str, chunk_index: int = 0) -> ChunkRecord:
    return ChunkRecord(
        id=chunk_id,
        text=text,
        metadata={"source_path": "docs/a.pdf", "chunk_index": chunk_index},
        dense_vector=[0.1, 0.2],
    )