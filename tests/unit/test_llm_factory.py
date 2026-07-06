from collections.abc import Mapping, Sequence

import pytest

from core.settings import (
    EvaluationSettings,
    ObservabilitySettings,
    ProviderModelSettings,
    RerankSettings,
    RetrievalSettings,
    Settings,
    VectorStoreSettings,
)
from libs.llm import BaseLLM, LLMFactory


class FakeLLM(BaseLLM):
    def __init__(self, config: ProviderModelSettings) -> None:
        self.config = config

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        return f"{self.config.provider}:{len(messages)}"


@pytest.fixture(autouse=True)
def reset_llm_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LLMFactory, "_providers", {})


def test_llm_factory_creates_registered_provider() -> None:
    settings = _settings_with_llm(provider="fake", model="fake-chat")
    LLMFactory.register_provider("fake", FakeLLM)

    llm = LLMFactory.create(settings)

    assert isinstance(llm, FakeLLM)
    assert llm.config.model == "fake-chat"
    assert llm.chat([{"role": "user", "content": "hello"}]) == "fake:1"


def test_llm_factory_normalizes_provider_names() -> None:
    settings = _settings_with_llm(provider="  FAKE  ", model="fake-chat")
    LLMFactory.register_provider("fake", FakeLLM)

    llm = LLMFactory.create(settings)

    assert isinstance(llm, FakeLLM)


def test_llm_factory_rejects_unknown_provider() -> None:
    settings = _settings_with_llm(provider="missing")

    with pytest.raises(ValueError, match="Unsupported LLM provider: missing"):
        LLMFactory.create(settings)


def _settings_with_llm(provider: str, model: str | None = None) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider=provider, model=model),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        vector_store=VectorStoreSettings(backend="chroma", persist_path="./data/db/chroma"),
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