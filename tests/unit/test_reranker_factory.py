from collections.abc import Sequence

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
from libs.reranker import BaseReranker, NoneReranker, RerankCandidate, RerankerFactory


class FakeReranker(BaseReranker):
    def __init__(self, config: RerankSettings) -> None:
        self.config = config

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        trace: object | None = None,
    ) -> list[RerankCandidate]:
        return sorted(candidates, key=lambda candidate: candidate["score"], reverse=True)


@pytest.fixture(autouse=True)
def reset_reranker_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RerankerFactory, "_backends", {"none": NoneReranker})


def test_reranker_factory_creates_none_reranker_by_default() -> None:
    settings = _settings_with_reranker(backend="none")

    reranker = RerankerFactory.create(settings)

    assert isinstance(reranker, NoneReranker)


def test_none_reranker_preserves_candidate_order() -> None:
    reranker = NoneReranker()
    candidates = [
        {"id": "chunk-1", "score": 0.2},
        {"id": "chunk-2", "score": 0.9},
    ]

    ranked = reranker.rerank("query", candidates)

    assert ranked == candidates
    assert ranked is not candidates


def test_reranker_factory_creates_registered_backend() -> None:
    settings = _settings_with_reranker(backend="fake", model="fake-reranker", top_m=5)
    RerankerFactory.register_backend("fake", FakeReranker)

    reranker = RerankerFactory.create(settings)
    ranked = reranker.rerank("query", [{"id": "low", "score": 0.1}, {"id": "high", "score": 0.8}])

    assert isinstance(reranker, FakeReranker)
    assert reranker.config.model == "fake-reranker"
    assert reranker.config.top_m == 5
    assert [candidate["id"] for candidate in ranked] == ["high", "low"]


def test_reranker_factory_normalizes_backend_names() -> None:
    settings = _settings_with_reranker(backend="  FAKE  ")
    RerankerFactory.register_backend("fake", FakeReranker)

    reranker = RerankerFactory.create(settings)

    assert isinstance(reranker, FakeReranker)


def test_reranker_factory_rejects_unknown_backend() -> None:
    settings = _settings_with_reranker(backend="missing")

    with pytest.raises(ValueError, match="Unsupported reranker backend: missing"):
        RerankerFactory.create(settings)


def test_reranker_factory_rejects_empty_backend_registration() -> None:
    with pytest.raises(ValueError, match="Reranker backend name must not be empty"):
        RerankerFactory.register_backend("  ", FakeReranker)


def _settings_with_reranker(backend: str, model: str | None = None, top_m: int | None = 30) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy="recursive", chunk_size=1000, chunk_overlap=200),
        vector_store=VectorStoreSettings(backend="chroma", persist_path="./data/db/chroma"),
        retrieval=RetrievalSettings(
            sparse_backend="bm25",
            fusion_algorithm="rrf",
            top_k_dense=20,
            top_k_sparse=20,
            top_k_final=10,
        ),
        rerank=RerankSettings(backend=backend, model=model, top_m=top_m),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )