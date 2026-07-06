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
from libs.reranker import CrossEncoderRerankError, CrossEncoderReranker, NoneReranker, RerankerFactory


@pytest.fixture(autouse=True)
def reset_reranker_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RerankerFactory, "_backends", {"none": NoneReranker})


def test_factory_routes_cross_encoder_backend() -> None:
    reranker = RerankerFactory.create(_settings_with_reranker(backend="cross_encoder", top_m=2))

    assert isinstance(reranker, CrossEncoderReranker)
    assert reranker.config.top_m == 2


def test_cross_encoder_reranker_orders_candidates_by_scorer_output() -> None:
    calls = []

    def scorer(query, candidates):
        calls.append((query, candidates))
        return [0.1, 0.9]

    reranker = CrossEncoderReranker(_rerank_settings(top_m=2), scorer=scorer)
    candidates = [
        {"id": "chunk-1", "text": "alpha", "score": 0.9},
        {"id": "chunk-2", "text": "beta", "score": 0.1},
    ]

    ranked = reranker.rerank("find beta", candidates)

    assert [candidate["id"] for candidate in ranked] == ["chunk-2", "chunk-1"]
    assert calls == [("find beta", candidates)]


def test_cross_encoder_reranker_limits_top_m_and_appends_remaining_candidates() -> None:
    def scorer(query, candidates):
        return [0.2, 0.8]

    reranker = CrossEncoderReranker(_rerank_settings(top_m=2), scorer=scorer)
    candidates = [
        {"id": "chunk-1", "text": "alpha"},
        {"id": "chunk-2", "text": "beta"},
        {"id": "chunk-3", "text": "gamma"},
    ]

    ranked = reranker.rerank("query", candidates)

    assert [candidate["id"] for candidate in ranked] == ["chunk-2", "chunk-1", "chunk-3"]


def test_cross_encoder_reranker_requires_scorer_for_rerank() -> None:
    reranker = CrossEncoderReranker(_rerank_settings())
    candidates = [{"id": "chunk-1", "text": "alpha"}]

    with pytest.raises(CrossEncoderRerankError, match="requires a scorer") as exc_info:
        reranker.rerank("query", candidates)

    assert exc_info.value.fallback_candidates == candidates


def test_cross_encoder_reranker_timeout_returns_fallback_signal() -> None:
    def scorer(query, candidates):
        raise TimeoutError

    reranker = CrossEncoderReranker(_rerank_settings(), scorer=scorer)
    candidates = [{"id": "chunk-1", "text": "alpha"}]

    with pytest.raises(CrossEncoderRerankError, match="scoring timed out") as exc_info:
        reranker.rerank("query", candidates)

    assert exc_info.value.fallback_candidates == candidates


def test_cross_encoder_reranker_failure_returns_fallback_signal() -> None:
    def scorer(query, candidates):
        raise RuntimeError("model unavailable")

    reranker = CrossEncoderReranker(_rerank_settings(), scorer=scorer)
    candidates = [{"id": "chunk-1", "text": "alpha"}]

    with pytest.raises(CrossEncoderRerankError, match="scoring failed: RuntimeError") as exc_info:
        reranker.rerank("query", candidates)

    assert exc_info.value.fallback_candidates == candidates


def test_cross_encoder_reranker_rejects_score_count_mismatch() -> None:
    def scorer(query, candidates):
        return [0.5]

    reranker = CrossEncoderReranker(_rerank_settings(), scorer=scorer)
    candidates = [{"id": "chunk-1", "text": "alpha"}, {"id": "chunk-2", "text": "beta"}]

    with pytest.raises(CrossEncoderRerankError, match="one score per candidate"):
        reranker.rerank("query", candidates)


def test_cross_encoder_reranker_rejects_invalid_candidate_shape() -> None:
    reranker = CrossEncoderReranker(_rerank_settings(), scorer=lambda query, candidates: [1.0])

    with pytest.raises(ValueError, match=r"cross_encoder reranker candidates\[0\].id must be a non-empty string"):
        reranker.rerank("query", [{"text": "alpha"}])


def _rerank_settings(top_m: int | None = 30) -> RerankSettings:
    return RerankSettings(backend="cross_encoder", model="mock-cross-encoder", top_m=top_m)


def _settings_with_reranker(backend: str, top_m: int | None = 30) -> Settings:
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
        rerank=RerankSettings(backend=backend, model="mock-cross-encoder", top_m=top_m),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )