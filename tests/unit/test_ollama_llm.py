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
from libs.llm import LLMFactory, LLMProviderError, OllamaLLM


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
def reset_llm_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LLMFactory, "_providers", {})


def test_factory_routes_ollama_provider() -> None:
    llm = LLMFactory.create(_settings_with_llm(_ollama_config()))

    assert isinstance(llm, OllamaLLM)


def test_ollama_chat_uses_local_http_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, response_text="local hello")
    llm = LLMFactory.create(
        _settings_with_llm(_ollama_config(base_url="http://ollama.example:11434", temperature=0.2, max_tokens=128))
    )

    response = llm.chat([{"role": "user", "content": "Say hello"}])

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    assert response == "local hello"
    assert request.full_url == "http://ollama.example:11434/api/chat"
    assert request.headers["Content-type"] == "application/json"
    assert body == {
        "model": "llama3",
        "messages": [{"role": "user", "content": "Say hello"}],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 128},
    }


def test_ollama_chat_uses_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, response_text="default hello")
    llm = LLMFactory.create(_settings_with_llm(_ollama_config(base_url=None)))

    assert llm.chat([{"role": "user", "content": "Say hello"}]) == "default hello"
    assert next(captured_requests).full_url == "http://localhost:11434/api/chat"


def test_ollama_connection_error_is_readable_and_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        raise URLError("connection refused for secret-token")

    monkeypatch.setattr("libs.llm.ollama_llm.urlopen", fake_urlopen)
    llm = LLMFactory.create(_settings_with_llm(_ollama_config(api_key="secret-token")))

    with pytest.raises(LLMProviderError) as exc_info:
        llm.chat([{"role": "user", "content": "Say hello"}])

    assert "ollama LLM request failed: URLError" in str(exc_info.value)
    assert "api_key" not in str(exc_info.value)


def test_ollama_rejects_invalid_message_shape() -> None:
    llm = LLMFactory.create(_settings_with_llm(_ollama_config()))

    with pytest.raises(ValueError, match=r"ollama LLM message\[0\].role must be a non-empty string"):
        llm.chat([{"role": "", "content": "Say hello"}])


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch, response_text: str) -> Iterator[Request]:
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        captured_requests.append(request)
        return FakeHTTPResponse({"message": {"role": "assistant", "content": response_text}})

    monkeypatch.setattr("libs.llm.ollama_llm.urlopen", fake_urlopen)
    return iter(captured_requests)


def _ollama_config(**overrides: object) -> ProviderModelSettings:
    values = {
        "provider": "ollama",
        "model": "llama3",
        "base_url": "http://localhost:11434",
    }
    values.update(overrides)
    return ProviderModelSettings(**values)


def _settings_with_llm(llm: ProviderModelSettings) -> Settings:
    return Settings(
        llm=llm,
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
        rerank=RerankSettings(backend="none", model=None, top_m=30),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )