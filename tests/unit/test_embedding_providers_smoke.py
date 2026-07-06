import json
from collections.abc import Iterator
from urllib.request import Request

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
from libs.embedding import AzureOpenAIEmbedding, EmbeddingFactory, OpenAIEmbedding


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@pytest.fixture(autouse=True)
def reset_embedding_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(EmbeddingFactory, "_providers", {})


def test_factory_routes_openai_and_azure_embedding_providers() -> None:
    assert isinstance(EmbeddingFactory.create(_settings_with_embedding(_embedding_config("openai"))), OpenAIEmbedding)
    assert isinstance(
        EmbeddingFactory.create(
            _settings_with_embedding(
                _embedding_config(
                    "azure",
                    azure_endpoint="https://resource.openai.azure.com/",
                    deployment_name="embedding-deployment",
                    api_version="2024-02-15-preview",
                )
            )
        ),
        AzureOpenAIEmbedding,
    )


def test_openai_embedding_uses_batch_http_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, embeddings=[[0.1, 0.2], [0.3, 0.4]])
    embedding = EmbeddingFactory.create(
        _settings_with_embedding(
            _embedding_config("openai", base_url="https://embedding.example/v1", dimensions=2)
        )
    )

    vectors = embedding.embed(["hello", "world"])

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert request.full_url == "https://embedding.example/v1/embeddings"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body == {
        "input": ["hello", "world"],
        "model": "text-embedding-3-small",
        "dimensions": 2,
    }


def test_azure_embedding_uses_deployment_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, embeddings=[[1.0, 2.0]])
    embedding = EmbeddingFactory.create(
        _settings_with_embedding(
            _embedding_config(
                "azure",
                azure_endpoint="https://resource.openai.azure.com/",
                deployment_name="embedding-deployment",
                api_version="2024-02-15-preview",
            )
        )
    )

    vectors = embedding.embed(["hello"])

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    assert vectors == [[1.0, 2.0]]
    assert request.full_url == (
        "https://resource.openai.azure.com/openai/deployments/embedding-deployment/"
        "embeddings?api-version=2024-02-15-preview"
    )
    assert request.headers["Api-key"] == "test-key"
    assert body == {"input": ["hello"]}


def test_embedding_rejects_empty_input() -> None:
    embedding = EmbeddingFactory.create(_settings_with_embedding(_embedding_config("openai")))

    with pytest.raises(ValueError, match="openai embedding texts must be a non-empty list"):
        embedding.embed([])


def test_embedding_rejects_empty_text_item() -> None:
    embedding = EmbeddingFactory.create(_settings_with_embedding(_embedding_config("openai")))

    with pytest.raises(ValueError, match=r"openai embedding texts\[1\] must be a non-empty string"):
        embedding.embed(["hello", ""])


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch, embeddings: list[list[float]]) -> Iterator[Request]:
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        captured_requests.append(request)
        data = [{"index": index, "embedding": vector} for index, vector in enumerate(embeddings)]
        return FakeHTTPResponse({"data": data})

    monkeypatch.setattr("libs.embedding.openai_embedding.urlopen", fake_urlopen)
    return iter(captured_requests)


def _embedding_config(provider: str, **overrides: object) -> ProviderModelSettings:
    values = {
        "provider": provider,
        "model": "text-embedding-3-small",
        "api_key": "test-key",
    }
    values.update(overrides)
    return ProviderModelSettings(**values)


def _settings_with_embedding(embedding: ProviderModelSettings) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=embedding,
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