from collections.abc import Mapping, Sequence

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
from libs.llm import BaseLLM
from libs.reranker import LLMRerankError, LLMReranker, RerankerFactory


class FakeLLM(BaseLLM):
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[Sequence[Mapping[str, str]]] = []

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        self.messages.append(messages)
        return self.response


@pytest.fixture(autouse=True)
def reset_reranker_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.reranker import NoneReranker

    monkeypatch.setattr(RerankerFactory, "_backends", {"none": NoneReranker})


def test_factory_routes_llm_backend() -> None:
    reranker = RerankerFactory.create(_settings_with_reranker(backend="llm", top_m=2))

    assert isinstance(reranker, LLMReranker)
    assert reranker.config.top_m == 2


def test_llm_reranker_orders_candidates_from_ranked_ids() -> None:
    llm = FakeLLM('{"ranked_ids": ["chunk-2", "chunk-1"]}')
    reranker = LLMReranker(_rerank_settings(top_m=2), llm=llm, prompt_template="Rank these chunks.")
    candidates = [
        {"id": "chunk-1", "text": "alpha", "score": 0.9, "metadata": {"source": "a.md"}},
        {"id": "chunk-2", "text": "beta", "score": 0.1, "metadata": {"source": "b.md"}},
    ]

    ranked = reranker.rerank("find beta", candidates)

    assert [candidate["id"] for candidate in ranked] == ["chunk-2", "chunk-1"]
    prompt = llm.messages[0][0]["content"]
    assert "Rank these chunks." in prompt
    assert '"query": "find beta"' in prompt
    assert '"id": "chunk-1"' in prompt


def test_llm_reranker_limits_top_m_and_appends_remaining_candidates() -> None:
    llm = FakeLLM('{"ranked_ids": ["chunk-2", "chunk-1"]}')
    reranker = LLMReranker(_rerank_settings(top_m=2), llm=llm, prompt_template="Rank.")
    candidates = [
        {"id": "chunk-1", "text": "alpha"},
        {"id": "chunk-2", "text": "beta"},
        {"id": "chunk-3", "text": "gamma"},
    ]

    ranked = reranker.rerank("query", candidates)

    assert [candidate["id"] for candidate in ranked] == ["chunk-2", "chunk-1", "chunk-3"]
    assert '"id": "chunk-3"' not in llm.messages[0][0]["content"]


def test_llm_reranker_rejects_malformed_json_with_fallback_candidates() -> None:
    llm = FakeLLM("not json")
    reranker = LLMReranker(_rerank_settings(), llm=llm, prompt_template="Rank.")
    candidates = [{"id": "chunk-1", "text": "alpha"}]

    with pytest.raises(LLMRerankError, match="response must be JSON with ranked_ids") as exc_info:
        reranker.rerank("query", candidates)

    assert exc_info.value.fallback_candidates == candidates


def test_llm_reranker_rejects_incomplete_ranked_ids() -> None:
    llm = FakeLLM('{"ranked_ids": ["chunk-1"]}')
    reranker = LLMReranker(_rerank_settings(), llm=llm, prompt_template="Rank.")
    candidates = [{"id": "chunk-1", "text": "alpha"}, {"id": "chunk-2", "text": "beta"}]

    with pytest.raises(LLMRerankError, match="ranked_ids must contain each candidate id exactly once"):
        reranker.rerank("query", candidates)


def test_llm_reranker_requires_llm_client_for_rerank() -> None:
    reranker = LLMReranker(_rerank_settings(), prompt_template="Rank.")
    candidates = [{"id": "chunk-1", "text": "alpha"}]

    with pytest.raises(LLMRerankError, match="requires an LLM client") as exc_info:
        reranker.rerank("query", candidates)

    assert exc_info.value.fallback_candidates == candidates


def test_llm_reranker_reads_prompt_from_path(tmp_path) -> None:
    prompt_path = tmp_path / "rerank.txt"
    prompt_path.write_text("Custom prompt", encoding="utf-8")

    reranker = LLMReranker(_rerank_settings(), llm=FakeLLM('{"ranked_ids": []}'), prompt_path=prompt_path)

    assert reranker.prompt_template == "Custom prompt"


def _rerank_settings(top_m: int | None = 30) -> RerankSettings:
    return RerankSettings(backend="llm", model="fake-reranker", top_m=top_m)


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
        rerank=RerankSettings(backend=backend, model="fake-reranker", top_m=top_m),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )