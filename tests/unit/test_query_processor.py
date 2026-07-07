import pytest

from core.query_engine import ProcessedQuery, QueryProcessor


def test_query_processor_extracts_keywords_and_sparse_query() -> None:
    processed = QueryProcessor().process("How does Hybrid RAG use BM25 and dense vectors?")

    assert isinstance(processed, ProcessedQuery)
    assert processed.semantic_query == "How does Hybrid RAG use BM25 and dense vectors?"
    assert processed.keywords == ["how", "does", "hybrid", "rag", "use", "bm25", "dense", "vectors"]
    assert processed.sparse_query == {
        "how": 1.0,
        "does": 1.0,
        "hybrid": 1.0,
        "rag": 1.0,
        "use": 1.0,
        "bm25": 1.0,
        "dense": 1.0,
        "vectors": 1.0,
    }


def test_query_processor_extracts_inline_filters_from_semantic_query() -> None:
    processed = QueryProcessor().process('collection:docs doc_type:pdf explain Azure Search source_path:"docs/a file.pdf"')

    assert processed.semantic_query == "explain Azure Search"
    assert processed.filters == {"collection": "docs", "doc_type": "pdf", "source_path": "docs/a file.pdf"}
    assert processed.keywords == ["explain", "azure", "search"]


def test_query_processor_merges_explicit_filters_over_inline_filters() -> None:
    processed = QueryProcessor().process(
        "collection:drafts query pipeline",
        filters={"collection": "docs", "language": "en", "unused": None},
    )

    assert processed.filters == {"collection": "docs", "language": "en"}


def test_query_processor_expands_aliases_into_sparse_query() -> None:
    processed = QueryProcessor(aliases={"rag": ["retrieval", "generation"]}).process("RAG pipeline")

    assert processed.keywords == ["rag", "pipeline"]
    assert processed.sparse_query == {"rag": 1.0, "retrieval": 0.5, "generation": 0.5, "pipeline": 1.0}


def test_query_processor_serializes_processed_query() -> None:
    processed = QueryProcessor().process("collection:docs hybrid search")

    assert processed.to_dict() == {
        "original_query": "collection:docs hybrid search",
        "semantic_query": "hybrid search",
        "keywords": ["hybrid", "search"],
        "sparse_query": {"hybrid": 1.0, "search": 1.0},
        "filters": {"collection": "docs"},
    }


def test_query_processor_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must be a non-empty string"):
        QueryProcessor().process("  ")


def test_query_processor_rejects_non_mapping_filters() -> None:
    with pytest.raises(ValueError, match="filters must be a mapping"):
        QueryProcessor().process("query", filters=[("collection", "docs")])  # type: ignore[arg-type]