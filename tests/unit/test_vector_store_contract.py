from collections.abc import Mapping, Sequence
from typing import Any

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
from libs.vector_store import BaseVectorStore, VectorStoreFactory


class FakeVectorStore(BaseVectorStore):
    def __init__(self, config: VectorStoreSettings) -> None:
        self.config = config
        self.records: list[Mapping[str, Any]] = []

    def upsert(self, records: Sequence[Mapping[str, Any]], trace: object | None = None) -> int:
        for record in records:
            _validate_record(record)
        self.records = list(records)
        return len(self.records)

    def query(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
        trace: object | None = None,
    ) -> list[Mapping[str, Any]]:
        if not vector or not all(isinstance(value, float) for value in vector):
            raise ValueError("query vector must be a non-empty sequence of floats")
        if top_k < 1:
            raise ValueError("top_k must be greater than zero")

        filtered_records = [record for record in self.records if _matches_filters(record, filters)]
        return [
            {"id": record["id"], "score": 1.0 / (index + 1), "metadata": record["metadata"], "text": record["text"]}
            for index, record in enumerate(filtered_records[:top_k])
        ]


@pytest.fixture(autouse=True)
def reset_vector_store_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(VectorStoreFactory, "_backends", {})


def test_vector_store_factory_creates_registered_backend() -> None:
    settings = _settings_with_vector_store(backend="fake", persist_path="./tmp/vector")
    VectorStoreFactory.register_backend("fake", FakeVectorStore)

    vector_store = VectorStoreFactory.create(settings)

    assert isinstance(vector_store, FakeVectorStore)
    assert vector_store.config.persist_path == "./tmp/vector"


def test_vector_store_factory_normalizes_backend_names() -> None:
    settings = _settings_with_vector_store(backend="  FAKE  ")
    VectorStoreFactory.register_backend("fake", FakeVectorStore)

    vector_store = VectorStoreFactory.create(settings)

    assert isinstance(vector_store, FakeVectorStore)


def test_vector_store_factory_rejects_unknown_backend() -> None:
    settings = _settings_with_vector_store(backend="missing")

    with pytest.raises(ValueError, match="Unsupported vector store backend: missing"):
        VectorStoreFactory.create(settings)


def test_vector_store_factory_rejects_empty_backend_registration() -> None:
    with pytest.raises(ValueError, match="Vector store backend name must not be empty"):
        VectorStoreFactory.register_backend("  ", FakeVectorStore)


def test_vector_store_contract_upserts_records_and_queries_results() -> None:
    vector_store = FakeVectorStore(VectorStoreSettings(backend="fake", persist_path="./tmp/vector"))
    records = [
        {"id": "chunk-1", "vector": [0.1, 0.2], "text": "alpha", "metadata": {"source": "a.md"}},
        {"id": "chunk-2", "vector": [0.3, 0.4], "text": "beta", "metadata": {"source": "b.md"}},
    ]

    written = vector_store.upsert(records)
    results = vector_store.query([0.1, 0.2], top_k=1)

    assert written == 2
    assert results == [{"id": "chunk-1", "score": 1.0, "metadata": {"source": "a.md"}, "text": "alpha"}]


def test_vector_store_contract_applies_metadata_filters() -> None:
    vector_store = FakeVectorStore(VectorStoreSettings(backend="fake", persist_path="./tmp/vector"))
    vector_store.upsert(
        [
            {"id": "chunk-1", "vector": [0.1], "text": "alpha", "metadata": {"collection": "docs"}},
            {"id": "chunk-2", "vector": [0.2], "text": "beta", "metadata": {"collection": "notes"}},
        ]
    )

    results = vector_store.query([0.1], top_k=10, filters={"collection": "notes"})

    assert [result["id"] for result in results] == ["chunk-2"]


def test_vector_store_contract_rejects_invalid_record_shape() -> None:
    vector_store = FakeVectorStore(VectorStoreSettings(backend="fake", persist_path="./tmp/vector"))

    with pytest.raises(ValueError, match="record.id must be a non-empty string"):
        vector_store.upsert([{"vector": [0.1], "text": "alpha", "metadata": {}}])


def test_vector_store_contract_rejects_invalid_query_shape() -> None:
    vector_store = FakeVectorStore(VectorStoreSettings(backend="fake", persist_path="./tmp/vector"))

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        vector_store.query([0.1], top_k=0)


def _validate_record(record: Mapping[str, Any]) -> None:
    if not isinstance(record.get("id"), str) or not record["id"].strip():
        raise ValueError("record.id must be a non-empty string")
    if not isinstance(record.get("vector"), list) or not all(isinstance(value, float) for value in record["vector"]):
        raise ValueError("record.vector must be a list of floats")
    if not isinstance(record.get("text"), str):
        raise ValueError("record.text must be a string")
    if not isinstance(record.get("metadata"), dict):
        raise ValueError("record.metadata must be a mapping")


def _matches_filters(record: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
    if filters is None:
        return True
    metadata = record["metadata"]
    return all(metadata.get(key) == value for key, value in filters.items())


def _settings_with_vector_store(backend: str, persist_path: str = "./data/db/chroma") -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy="recursive", chunk_size=1000, chunk_overlap=200),
        vector_store=VectorStoreSettings(backend=backend, persist_path=persist_path),
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