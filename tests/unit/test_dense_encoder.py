from core import Chunk, ChunkRecord
from ingestion.embedding import DenseEncoder
from libs.embedding import BaseEmbedding

import pytest


class FakeEmbedding(BaseEmbedding):
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str], trace: object | None = None) -> list[list[float]]:
        self.calls.append(texts)
        return self.vectors


def test_dense_encoder_encodes_chunks_to_chunk_records() -> None:
    embedding = FakeEmbedding([[0.1, 0.2], [0.3, 0.4]])
    chunks = [_chunk("chunk-1", "Alpha"), _chunk("chunk-2", "Beta")]

    records = DenseEncoder(embedding=embedding).encode_chunks(chunks)

    assert [type(record) for record in records] == [ChunkRecord, ChunkRecord]
    assert embedding.calls == [["Alpha", "Beta"]]
    assert [record.id for record in records] == ["chunk-1", "chunk-2"]
    assert [record.text for record in records] == ["Alpha", "Beta"]
    assert [record.dense_vector for record in records] == [[0.1, 0.2], [0.3, 0.4]]
    assert records[0].metadata == {"source_path": "docs/a.pdf", "chunk_index": 0}
    assert chunks[0].metadata == {"source_path": "docs/a.pdf", "chunk_index": 0}


def test_dense_encoder_encodes_single_chunk() -> None:
    record = DenseEncoder(embedding=FakeEmbedding([[1.0, 2.0, 3.0]])).encode_chunk(_chunk("chunk-1", "Alpha"))

    assert record.id == "chunk-1"
    assert record.dense_vector == [1.0, 2.0, 3.0]


def test_dense_encoder_returns_empty_records_without_embedding_call() -> None:
    embedding = FakeEmbedding([])

    assert DenseEncoder(embedding=embedding).encode_chunks([]) == []
    assert embedding.calls == []


def test_dense_encoder_rejects_vector_count_mismatch() -> None:
    encoder = DenseEncoder(embedding=FakeEmbedding([[0.1, 0.2]]))

    with pytest.raises(ValueError, match="embedding returned 1 vectors for 2 chunks"):
        encoder.encode_chunks([_chunk("chunk-1", "Alpha"), _chunk("chunk-2", "Beta")])


def test_dense_encoder_rejects_inconsistent_dimensions() -> None:
    encoder = DenseEncoder(embedding=FakeEmbedding([[0.1, 0.2], [0.3]]))

    with pytest.raises(ValueError, match="consistent dimensions"):
        encoder.encode_chunks([_chunk("chunk-1", "Alpha"), _chunk("chunk-2", "Beta")])


def test_dense_encoder_rejects_non_float_vectors() -> None:
    encoder = DenseEncoder(embedding=FakeEmbedding([[0.1, 1]]))  # type: ignore[list-item]

    with pytest.raises(ValueError, match="must contain floats"):
        encoder.encode_chunk(_chunk("chunk-1", "Alpha"))


def test_dense_encoder_requires_settings_or_embedding_client() -> None:
    with pytest.raises(ValueError, match="requires either settings or an embedding client"):
        DenseEncoder()


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata={"source_path": "docs/a.pdf", "chunk_index": int(chunk_id.rsplit("-", 1)[1]) - 1},
        start_offset=0,
        end_offset=len(text),
        source_ref="doc-1",
    )