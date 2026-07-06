import pytest

from core.settings import (
    EvaluationSettings,
    ObservabilitySettings,
    ProviderModelSettings,
    RerankSettings,
    RetrievalSettings,
    Settings,
    SplitterSettings,
    VectorStoreSettings,
)
from libs.vector_store import ChromaStore, VectorStoreFactory


@pytest.fixture(autouse=True)
def reset_vector_store_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(VectorStoreFactory, "_backends", {})


def test_factory_routes_chroma_backend(tmp_path) -> None:
    vector_store = VectorStoreFactory.create(_settings_with_vector_store(persist_path=str(tmp_path / "chroma")))

    assert isinstance(vector_store, ChromaStore)


def test_chroma_store_upsert_query_roundtrip(tmp_path) -> None:
    vector_store = VectorStoreFactory.create(_settings_with_vector_store(persist_path=str(tmp_path / "chroma")))
    records = [
        {"id": "chunk-1", "vector": [1.0, 0.0], "text": "alpha text", "metadata": {"source": "a.md"}},
        {"id": "chunk-2", "vector": [0.0, 1.0], "text": "beta text", "metadata": {"source": "b.md"}},
    ]

    written = vector_store.upsert(records)
    results = vector_store.query([1.0, 0.0], top_k=1)

    assert written == 2
    assert results[0]["id"] == "chunk-1"
    assert results[0]["text"] == "alpha text"
    assert results[0]["metadata"] == {"source": "a.md"}
    assert 0.0 < results[0]["score"] <= 1.0


def test_chroma_store_respects_top_k(tmp_path) -> None:
    vector_store = VectorStoreFactory.create(_settings_with_vector_store(persist_path=str(tmp_path / "chroma")))
    vector_store.upsert(
        [
            {"id": "chunk-1", "vector": [1.0, 0.0], "text": "alpha", "metadata": {"source": "a.md"}},
            {"id": "chunk-2", "vector": [0.8, 0.2], "text": "beta", "metadata": {"source": "b.md"}},
            {"id": "chunk-3", "vector": [0.0, 1.0], "text": "gamma", "metadata": {"source": "c.md"}},
        ]
    )

    results = vector_store.query([1.0, 0.0], top_k=2)

    assert len(results) == 2
    assert [result["id"] for result in results] == ["chunk-1", "chunk-2"]


def test_chroma_store_applies_metadata_filters(tmp_path) -> None:
    vector_store = VectorStoreFactory.create(_settings_with_vector_store(persist_path=str(tmp_path / "chroma")))
    vector_store.upsert(
        [
            {
                "id": "chunk-1",
                "vector": [1.0, 0.0],
                "text": "alpha",
                "metadata": {"collection": "docs", "source": "a.md"},
            },
            {
                "id": "chunk-2",
                "vector": [0.9, 0.1],
                "text": "beta",
                "metadata": {"collection": "notes", "source": "b.md"},
            },
        ]
    )

    results = vector_store.query([1.0, 0.0], top_k=10, filters={"collection": "notes"})

    assert [result["id"] for result in results] == ["chunk-2"]


def test_chroma_store_rejects_invalid_query_shape(tmp_path) -> None:
    vector_store = VectorStoreFactory.create(_settings_with_vector_store(persist_path=str(tmp_path / "chroma")))

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        vector_store.query([1.0], top_k=0)


def _settings_with_vector_store(persist_path: str) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy="recursive", chunk_size=1000, chunk_overlap=200),
        vector_store=VectorStoreSettings(backend="chroma", persist_path=persist_path),
        retrieval=RetrievalSettings(
            sparse_backend="bm25",
            fusion_algorithm="rrf",
            top_k_dense=20,
            top_k_sparse=20,
            top_k_final=10,
        ),
        rerank=RerankSettings(backend="none", model=None, top_m=30),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )