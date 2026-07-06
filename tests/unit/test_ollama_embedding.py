import json
from collections.abc import Iterator
from urllib.error import URLError
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
from libs.embedding import EmbeddingFactory, EmbeddingProviderError, OllamaEmbedding


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


def test_factory_routes_ollama_embedding_provider() -> None:
    embedding = EmbeddingFactory.create(_settings_with_embedding(_ollama_config()))

    assert isinstance(embedding, OllamaEmbedding)


def test_ollama_embedding_uses_batch_http_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    embedding = EmbeddingFactory.create(
        _settings_with_embedding(_ollama_config(base_url="http://ollama.example:11434"))
    )

    vectors = embedding.embed(["hello", "world"])

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert request.full_url == "http://ollama.example:11434/api/embed"
    assert request.headers["Content-type"] == "application/json"
    assert body == {"model": "nomic-embed-text", "input": ["hello", "world"]}


def test_ollama_embedding_uses_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, embeddings=[[1.0, 2.0]])
    embedding = EmbeddingFactory.create(_settings_with_embedding(_ollama_config(base_url=None)))

    assert embedding.embed(["hello"]) == [[1.0, 2.0]]
    assert next(captured_requests).full_url == "http://localhost:11434/api/embed"


def test_ollama_embedding_rejects_empty_input() -> None:
    embedding = EmbeddingFactory.create(_settings_with_embedding(_ollama_config()))

    with pytest.raises(ValueError, match="ollama embedding texts must be a non-empty list"):
        embedding.embed([])


def test_ollama_embedding_rejects_oversized_text() -> None:
    embedding = EmbeddingFactory.create(_settings_with_embedding(_ollama_config()))

    with pytest.raises(ValueError, match=r"ollama embedding texts\[0\] exceeds max_input_chars=32768"):
        embedding.embed(["x" * (OllamaEmbedding.max_input_chars + 1)])


def test_ollama_connection_error_is_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        raise URLError("connection refused")

    monkeypatch.setattr("libs.embedding.ollama_embedding.urlopen", fake_urlopen)
    embedding = EmbeddingFactory.create(_settings_with_embedding(_ollama_config()))

    with pytest.raises(EmbeddingProviderError, match="ollama embedding request failed: URLError connection refused"):
        embedding.embed(["hello"])


def test_ollama_timeout_error_is_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        raise TimeoutError

    monkeypatch.setattr("libs.embedding.ollama_embedding.urlopen", fake_urlopen)
    embedding = EmbeddingFactory.create(_settings_with_embedding(_ollama_config()))

    with pytest.raises(EmbeddingProviderError, match="ollama embedding request failed: TimeoutError"):
        embedding.embed(["hello"])


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch, embeddings: list[list[float]]) -> Iterator[Request]:
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        captured_requests.append(request)
        return FakeHTTPResponse({"embeddings": embeddings})

    monkeypatch.setattr("libs.embedding.ollama_embedding.urlopen", fake_urlopen)
    return iter(captured_requests)


def _ollama_config(**overrides: object) -> ProviderModelSettings:
    values = {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "base_url": "http://localhost:11434",
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