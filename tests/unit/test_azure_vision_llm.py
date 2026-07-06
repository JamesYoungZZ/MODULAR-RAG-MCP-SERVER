import base64
import json
from collections.abc import Iterator
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from PIL import Image

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
from libs.llm import AzureVisionLLM, LLMFactory, LLMProviderError


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
def reset_vision_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LLMFactory, "_vision_providers", {})


def test_factory_routes_azure_vision_provider() -> None:
    vision_llm = LLMFactory.create_vision_llm(_settings_with_vision())

    assert isinstance(vision_llm, AzureVisionLLM)


def test_azure_vision_chat_uses_multimodal_http_shape(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured_requests = _capture_urlopen(monkeypatch, response_text="image description")
    image_path = _write_png(tmp_path / "sample.png", size=(8, 6))
    vision_llm = LLMFactory.create_vision_llm(_settings_with_vision(max_tokens=128, temperature=0.1))

    response = vision_llm.chat_with_image("Describe this image", image_path)

    request = next(captured_requests)
    body = json.loads(request.data.decode("utf-8"))
    content = body["messages"][0]["content"]
    assert response == "image description"
    assert request.full_url == (
        "https://resource.openai.azure.com/openai/deployments/vision-deployment/"
        "chat/completions?api-version=2024-02-15-preview"
    )
    assert request.headers["Api-key"] == "test-key"
    assert body["temperature"] == 0.1
    assert body["max_tokens"] == 128
    assert content[0] == {"type": "text", "text": "Describe this image"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_azure_vision_supports_base64_string_input(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured_requests = _capture_urlopen(monkeypatch, response_text="base64 description")
    image_path = _write_png(tmp_path / "sample.png", size=(5, 5))
    encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    vision_llm = LLMFactory.create_vision_llm(_settings_with_vision())

    assert vision_llm.chat_with_image("Describe", encoded_image) == "base64 description"
    body = json.loads(next(captured_requests).data.decode("utf-8"))
    image_url = body["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")


def test_azure_vision_compresses_large_images(tmp_path) -> None:
    image_path = _write_png(tmp_path / "large.png", size=(40, 20))
    vision_llm = LLMFactory.create_vision_llm(_settings_with_vision(max_image_size=10))

    data_url = vision_llm.preprocess_image(image_path)
    encoded_image = data_url.split(",", 1)[1]
    resized_bytes = base64.b64decode(encoded_image)

    with Image.open(BytesIO(resized_bytes)) as image:
        assert image.width <= 10
        assert image.height <= 10


def test_azure_vision_timeout_error_is_readable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        raise TimeoutError

    monkeypatch.setattr("libs.llm.azure_vision_llm.urlopen", fake_urlopen)
    image_path = _write_png(tmp_path / "sample.png", size=(4, 4))
    vision_llm = LLMFactory.create_vision_llm(_settings_with_vision())

    with pytest.raises(LLMProviderError, match="azure vision LLM request failed: TimeoutError"):
        vision_llm.chat_with_image("Describe", image_path)


def test_azure_vision_auth_failure_includes_azure_error_code(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("libs.llm.azure_vision_llm.urlopen", fake_urlopen)
    image_path = _write_png(tmp_path / "sample.png", size=(4, 4))
    vision_llm = LLMFactory.create_vision_llm(_settings_with_vision())

    with pytest.raises(LLMProviderError, match="azure vision LLM request failed: AzureHTTPError 401"):
        vision_llm.chat_with_image("Describe", image_path)


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch, response_text: str) -> Iterator[Request]:
    captured_requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        captured_requests.append(request)
        return FakeHTTPResponse({"choices": [{"message": {"content": response_text}}]})

    monkeypatch.setattr("libs.llm.azure_vision_llm.urlopen", fake_urlopen)
    return iter(captured_requests)


def _write_png(path, size: tuple[int, int]):
    image = Image.new("RGB", size, color="red")
    image.save(path, format="PNG")
    return path


def _settings_with_vision(
    max_image_size: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> Settings:
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
        rerank=RerankSettings(backend="none", model=None, top_m=30),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
        vision_llm=ProviderModelSettings(
            provider="azure",
            model="gpt-4o",
            deployment_name="vision-deployment",
            azure_endpoint="https://resource.openai.azure.com/",
            api_version="2024-02-15-preview",
            api_key="test-key",
            max_image_size=max_image_size,
            max_tokens=max_tokens,
            temperature=temperature,
        ),
    )