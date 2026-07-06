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
from libs.splitter import BaseSplitter, SplitterFactory


class FakeSplitter(BaseSplitter):
    def __init__(self, config: SplitterSettings) -> None:
        self.config = config

    def split_text(self, text: str, trace: object | None = None) -> list[str]:
        return [part.strip() for part in text.split("|") if part.strip()]


@pytest.fixture(autouse=True)
def reset_splitter_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SplitterFactory, "_strategies", {})


def test_splitter_factory_creates_registered_strategy() -> None:
    settings = _settings_with_splitter(strategy="fake", chunk_size=500, chunk_overlap=50)
    SplitterFactory.register_strategy("fake", FakeSplitter)

    splitter = SplitterFactory.create(settings)

    assert isinstance(splitter, FakeSplitter)
    assert splitter.config.chunk_size == 500
    assert splitter.config.chunk_overlap == 50
    assert splitter.split_text("alpha | beta") == ["alpha", "beta"]


def test_splitter_factory_normalizes_strategy_names() -> None:
    settings = _settings_with_splitter(strategy="  FAKE  ")
    SplitterFactory.register_strategy("fake", FakeSplitter)

    splitter = SplitterFactory.create(settings)

    assert isinstance(splitter, FakeSplitter)


def test_splitter_factory_rejects_unknown_strategy() -> None:
    settings = _settings_with_splitter(strategy="missing")

    with pytest.raises(ValueError, match="Unsupported splitter strategy: missing"):
        SplitterFactory.create(settings)


def test_splitter_factory_rejects_empty_strategy_registration() -> None:
    with pytest.raises(ValueError, match="Splitter strategy name must not be empty"):
        SplitterFactory.register_strategy("  ", FakeSplitter)


def _settings_with_splitter(
    strategy: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy=strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap),
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