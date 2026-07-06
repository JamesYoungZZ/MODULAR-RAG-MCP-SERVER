"""Dense vector encoder for ingestion chunks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core import Chunk, ChunkRecord
from core.settings import Settings
from libs.embedding import BaseEmbedding, EmbeddingFactory


class DenseEncoder:
    """Encode Chunk text into dense vectors and return ChunkRecord objects."""

    def __init__(self, settings: Settings | None = None, embedding: BaseEmbedding | None = None) -> None:
        if embedding is None and settings is None:
            raise ValueError("dense encoder requires either settings or an embedding client")
        self.embedding = embedding or EmbeddingFactory.create(settings)  # type: ignore[arg-type]

    def encode_chunks(self, chunks: Sequence[Chunk], trace: Any | None = None) -> list[ChunkRecord]:
        chunk_list = list(chunks)
        if not chunk_list:
            return []

        vectors = self.embedding.embed([chunk.text for chunk in chunk_list], trace=trace)
        _validate_vectors(vectors, expected_count=len(chunk_list))
        return [
            ChunkRecord(
                id=chunk.id,
                text=chunk.text,
                metadata=dict(chunk.metadata),
                dense_vector=vector,
            )
            for chunk, vector in zip(chunk_list, vectors, strict=True)
        ]

    def encode_chunk(self, chunk: Chunk, trace: Any | None = None) -> ChunkRecord:
        return self.encode_chunks([chunk], trace=trace)[0]


def _validate_vectors(vectors: list[list[float]], expected_count: int) -> None:
    if len(vectors) != expected_count:
        raise ValueError(f"embedding returned {len(vectors)} vectors for {expected_count} chunks")
    if not vectors:
        return

    dimension = len(vectors[0])
    if dimension == 0:
        raise ValueError("embedding vectors must not be empty")
    for index, vector in enumerate(vectors):
        if len(vector) != dimension:
            raise ValueError("embedding vectors must have consistent dimensions")
        if not all(isinstance(value, float) for value in vector):
            raise ValueError(f"embedding vector at index {index} must contain floats")


__all__ = ["DenseEncoder"]