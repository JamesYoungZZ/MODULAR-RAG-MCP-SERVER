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
from libs.embedding import BaseEmbedding, EmbeddingFactory


class FakeEmbedding(BaseEmbedding):
    def __init__(self, config: ProviderModelSettings) -> None:
        self.config = config

    def embed(self, texts: list[str], trace: object | None = None) -> list[list[float]]:
        return [[float(len(text)), float(index)] for index, text in enumerate(texts)]


@pytest.fixture(autouse=True)
def reset_embedding_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(EmbeddingFactory, "_providers", {})


def test_embedding_factory_creates_registered_provider() -> None:
    settings = _settings_with_embedding(provider="fake", model="fake-embedding")
    EmbeddingFactory.register_provider("fake", FakeEmbedding)

    embedding = EmbeddingFactory.create(settings)

    assert isinstance(embedding, FakeEmbedding)
    assert embedding.config.model == "fake-embedding"
    assert embedding.embed(["hello", "world!"]) == [[5.0, 0.0], [6.0, 1.0]]


def test_embedding_factory_normalizes_provider_names() -> None:
    settings = _settings_with_embedding(provider="  FAKE  ", model="fake-embedding")
    EmbeddingFactory.register_provider("fake", FakeEmbedding)

    embedding = EmbeddingFactory.create(settings)

    assert isinstance(embedding, FakeEmbedding)


def test_embedding_factory_rejects_unknown_provider() -> None:
    settings = _settings_with_embedding(provider="missing")

    with pytest.raises(ValueError, match="Unsupported embedding provider: missing"):
        EmbeddingFactory.create(settings)


def _settings_with_embedding(provider: str, model: str | None = None) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider=provider, model=model),
        splitter=SplitterSettings(strategy="recursive", chunk_size=1000, chunk_overlap=200),
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