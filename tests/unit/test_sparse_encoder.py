from core import Chunk, ChunkRecord
from ingestion.embedding import SparseEncoder


def test_sparse_encoder_encodes_term_frequencies_to_chunk_records() -> None:
    chunks = [
        _chunk("chunk-1", "BM25 search search improves exact keyword recall."),
        _chunk("chunk-2", "Dense vectors improve semantic recall."),
    ]

    records = SparseEncoder().encode_chunks(chunks)

    assert [type(record) for record in records] == [ChunkRecord, ChunkRecord]
    assert [record.id for record in records] == ["chunk-1", "chunk-2"]
    assert records[0].text == chunks[0].text
    assert records[0].sparse_vector == {
        "bm25": 1.0,
        "exact": 1.0,
        "improves": 1.0,
        "keyword": 1.0,
        "recall": 1.0,
        "search": 2.0,
    }
    assert records[0].metadata == {
        "source_path": "docs/a.pdf",
        "chunk_index": 0,
        "sparse_doc_length": 7,
        "sparse_unique_terms": 6,
    }
    assert chunks[0].metadata == {"source_path": "docs/a.pdf", "chunk_index": 0}


def test_sparse_encoder_filters_default_stopwords() -> None:
    record = SparseEncoder().encode_chunk(_chunk("chunk-1", "The RAG system is for search and retrieval."))

    assert record.sparse_vector == {"rag": 1.0, "retrieval": 1.0, "search": 1.0, "system": 1.0}
    assert record.metadata["sparse_doc_length"] == 4


def test_sparse_encoder_supports_custom_stopwords() -> None:
    record = SparseEncoder(stopwords={"rag", "search"}).encode_chunk(_chunk("chunk-1", "RAG search search retrieval"))

    assert record.sparse_vector == {"retrieval": 1.0}
    assert record.metadata["sparse_doc_length"] == 1


def test_sparse_encoder_has_explicit_empty_text_behavior() -> None:
    record = SparseEncoder().encode_chunk(_chunk("chunk-1", "   ... ---   "))

    assert record.sparse_vector == {}
    assert record.metadata["sparse_doc_length"] == 0
    assert record.metadata["sparse_unique_terms"] == 0


def test_sparse_encoder_returns_empty_records_for_empty_input() -> None:
    assert SparseEncoder().encode_chunks([]) == []


def test_sparse_encoder_tokenizes_numbers_and_hyphenated_terms() -> None:
    record = SparseEncoder().encode_chunk(_chunk("chunk-1", "GPT-4o RRF rank-fusion top_k 10 10"))

    assert record.sparse_vector == {"10": 2.0, "gpt-4o": 1.0, "rank-fusion": 1.0, "rrf": 1.0, "top_k": 1.0}


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata={"source_path": "docs/a.pdf", "chunk_index": int(chunk_id.rsplit("-", 1)[1]) - 1},
        start_offset=0,
        end_offset=len(text),
        source_ref="doc-1",
    )