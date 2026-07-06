"""Idempotent vector-store upsert for dense chunk records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from core import ChunkRecord
from core.settings import Settings
from libs.vector_store import BaseVectorStore, VectorStoreFactory


class VectorUpserter:
    """Convert dense ChunkRecord objects into stable vector-store records."""

    def __init__(self, settings: Settings | None = None, vector_store: BaseVectorStore | None = None) -> None:
        if vector_store is None and settings is None:
            raise ValueError("vector upserter requires either settings or a vector store client")
        self.vector_store = vector_store or VectorStoreFactory.create(settings)  # type: ignore[arg-type]

    def upsert_records(self, records: Sequence[ChunkRecord], trace: Any | None = None) -> int:
        vector_records = [self.to_vector_record(record) for record in records]
        return self.vector_store.upsert(vector_records, trace=trace)

    def to_vector_record(self, record: ChunkRecord) -> dict[str, Any]:
        vector_record = record.to_vector_record()
        stable_id = stable_chunk_id(record)
        metadata = dict(record.metadata)
        metadata["original_chunk_id"] = record.id
        metadata["content_hash"] = _content_hash(record.text)
        return {
            "id": stable_id,
            "vector": vector_record["vector"],
            "text": vector_record["text"],
            "metadata": metadata,
        }


def stable_chunk_id(record: ChunkRecord) -> str:
    source_path = _required_metadata_string(record.metadata, "source_path")
    chunk_index = record.metadata.get("chunk_index")
    if not isinstance(chunk_index, int) or isinstance(chunk_index, bool) or chunk_index < 0:
        raise ValueError("metadata.chunk_index must be a non-negative integer for vector upsert")
    digest_input = f"{source_path}|{chunk_index}|{_content_hash(record.text)[:8]}"
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def _required_metadata_string(metadata: Mapping[str, Any], field_name: str) -> str:
    value = metadata.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"metadata.{field_name} must be a non-empty string for vector upsert")
    return value


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["VectorUpserter", "stable_chunk_id"]