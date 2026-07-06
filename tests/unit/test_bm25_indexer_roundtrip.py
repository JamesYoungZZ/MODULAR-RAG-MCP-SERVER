import math

import pytest

from core import ChunkRecord
from ingestion.storage import BM25Indexer


def test_bm25_indexer_build_save_load_query_roundtrip(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())
    indexer.save()

    loaded = BM25Indexer(tmp_path).load()
    results = loaded.query("alpha", top_k=2)

    assert [result.id for result in results] == ["chunk-1", "chunk-3"]
    assert results[0].text == "alpha alpha beta"
    assert results[0].metadata["source_path"] == "docs/a.pdf"
    assert results[0].score >= results[1].score


def test_bm25_indexer_computes_idf_with_spec_formula(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())

    assert indexer.index["beta"]["idf"] == pytest.approx(math.log((3 - 2 + 0.5) / (2 + 0.5)))
    assert indexer.index["gamma"]["idf"] == pytest.approx(math.log((3 - 1 + 0.5) / (1 + 0.5)))
    assert indexer.document_count == 3
    assert indexer.average_doc_length == pytest.approx((3 + 2 + 2) / 3)


def test_bm25_indexer_persists_inverted_index_shape(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())

    alpha_entry = indexer.index["alpha"]

    assert sorted(alpha_entry) == ["idf", "postings"]
    assert alpha_entry["postings"] == [
        {"chunk_id": "chunk-1", "tf": 2.0, "doc_length": 3.0},
        {"chunk_id": "chunk-3", "tf": 1.0, "doc_length": 2.0},
    ]


def test_bm25_indexer_upsert_replaces_existing_chunk_and_adds_new_chunk(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())

    written = indexer.upsert(
        [
            _record("chunk-2", "docs/b.pdf", {"delta": 3.0}),
            _record("chunk-4", "docs/d.pdf", {"epsilon": 1.0}),
        ]
    )

    assert written == 2
    assert indexer.document_count == 4
    assert [result.id for result in indexer.query("delta", top_k=3)] == ["chunk-2"]
    assert [result.id for result in indexer.query("gamma", top_k=3)] == []
    assert [result.id for result in indexer.query("epsilon", top_k=3)] == ["chunk-4"]


def test_bm25_indexer_build_recreates_index_from_scratch(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())

    indexer.build([_record("chunk-new", "docs/new.pdf", {"omega": 1.0})])

    assert indexer.document_count == 1
    assert indexer.query("alpha") == []
    assert [result.id for result in indexer.query("omega")] == ["chunk-new"]


def test_bm25_indexer_queries_sparse_vector_mapping(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())

    assert [result.id for result in indexer.query({"gamma": 2.0}, top_k=1)] == ["chunk-2"]


def test_bm25_indexer_rejects_invalid_top_k(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path).build(_records())

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        indexer.query("alpha", top_k=0)


def test_bm25_indexer_requires_sparse_vector(tmp_path) -> None:
    indexer = BM25Indexer(tmp_path)
    record = ChunkRecord(id="chunk-1", text="text", metadata={"source_path": "docs/a.pdf"})

    with pytest.raises(ValueError, match="sparse_vector is required"):
        indexer.upsert([record])


def _records() -> list[ChunkRecord]:
    return [
        _record("chunk-1", "docs/a.pdf", {"alpha": 2.0, "beta": 1.0}),
        _record("chunk-2", "docs/b.pdf", {"beta": 1.0, "gamma": 1.0}),
        _record("chunk-3", "docs/c.pdf", {"alpha": 1.0, "zeta": 1.0}),
    ]


def _record(chunk_id: str, source_path: str, sparse_vector: dict[str, float]) -> ChunkRecord:
    text = " ".join(term for term, count in sparse_vector.items() for _ in range(int(count)))
    return ChunkRecord(
        id=chunk_id,
        text=text,
        metadata={"source_path": source_path, "sparse_doc_length": int(sum(sparse_vector.values()))},
        sparse_vector=sparse_vector,
    )