import json
from collections.abc import Iterator
from io import BytesIO
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
from libs.llm import AzureOpenAILLM, DeepSeekLLM, LLMFactory, OpenAICompatibleLLM


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


def test_factory_routes_openai_compatible_providers() -> None:
    assert isinstance(LLMFactory.create(_settings_with_llm(_provider_config("openai"))), OpenAICompatibleLLM)
    assert isinstance(
        LLMFactory.create(
            _settings_with_llm(
                _provider_config(
                    "azure",
                    azure_endpoint="https://resource.openai.azure.com/",
                    deployment_name="chat-deployment",
                    api_version="2024-02-15-preview",
                )
            )
        ),
        AzureOpenAILLM,
    )
    assert isinstance(LLMFactory.create(_settings_with_llm(_provider_config("deepseek"))), DeepSeekLLM)


def test_openai_chat_uses_compatible_http_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, response_text="hello")
    llm = LLMFactory.create(_settings_with_llm(_provider_config("openai", base_url="https://llm.example/v1")))

    response = llm.chat([{"role": "user", "content": "Say hello"}])

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    assert response == "hello"
    assert request.full_url == "https://llm.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body["model"] == "gpt-test"
    assert body["messages"] == [{"role": "user", "content": "Say hello"}]


def test_azure_chat_uses_deployment_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = _capture_urlopen(monkeypatch, response_text="azure hello")
    llm = LLMFactory.create(
        _settings_with_llm(
            _provider_config(
                "azure",
                azure_endpoint="https://resource.openai.azure.com/",
                deployment_name="chat-deployment",
                api_version="2024-02-15-preview",
            )
        )
    )

    response = llm.chat([{"role": "user", "content": "Say hello"}])

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    assert response == "azure hello"
    assert request.full_url == (
        "https://resource.openai.azure.com/openai/deployments/chat-deployment/"
        "chat/completions?api-version=2024-02-15-preview"
    )
    assert request.headers["Api-key"] == "test-key"
    assert "model" not in body


def test_chat_rejects_invalid_message_shape() -> None:
    llm = LLMFactory.create(_settings_with_llm(_provider_config("openai")))

    with pytest.raises(ValueError, match=r"openai LLM message\[0\].content must be a non-empty string"):
        llm.chat([{"role": "user", "content": ""}])


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch, response_text: str) -> Iterator[Request]:
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        captured_requests.append(request)
        return FakeHTTPResponse({"choices": [{"message": {"content": response_text}}]})

    monkeypatch.setattr("libs.llm.openai_llm.urlopen", fake_urlopen)
    return iter(captured_requests)


def _provider_config(provider: str, **overrides: object) -> ProviderModelSettings:
    values = {
        "provider": provider,
        "model": "gpt-test",
        "api_key": "test-key",
        "temperature": 0.0,
        "max_tokens": 64,
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