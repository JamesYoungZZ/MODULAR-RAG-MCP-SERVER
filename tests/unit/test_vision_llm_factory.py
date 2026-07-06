from pathlib import Path
from typing import Any

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
from libs.llm import BaseVisionLLM, ImageInput, LLMFactory


class FakeVisionLLM(BaseVisionLLM):
    def __init__(self, config: ProviderModelSettings) -> None:
        self.config = config
        self.calls: list[tuple[str, ImageInput, Any | None]] = []

    def chat_with_image(self, text: str, image_path: ImageInput, trace: Any | None = None) -> str:
        self.calls.append((text, image_path, trace))
        return f"{self.config.provider}:{self.config.model}:{type(image_path).__name__}"

    def preprocess_image(self, image_path: ImageInput) -> ImageInput:
        if isinstance(image_path, Path):
            return str(image_path)
        return image_path


@pytest.fixture(autouse=True)
def reset_vision_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LLMFactory, "_vision_providers", {})


def test_vision_llm_factory_creates_registered_provider() -> None:
    settings = _settings_with_vision(provider="fake-vision", model="fake-model", max_image_size=1024)
    LLMFactory.register_vision_provider("fake-vision", FakeVisionLLM)

    vision_llm = LLMFactory.create_vision_llm(settings)

    assert isinstance(vision_llm, FakeVisionLLM)
    assert vision_llm.config.model == "fake-model"
    assert vision_llm.config.max_image_size == 1024
    assert vision_llm.chat_with_image("describe", "image.png") == "fake-vision:fake-model:str"


def test_vision_llm_factory_normalizes_provider_names() -> None:
    settings = _settings_with_vision(provider="  FAKE-VISION  ")
    LLMFactory.register_vision_provider("fake-vision", FakeVisionLLM)

    vision_llm = LLMFactory.create_vision_llm(settings)

    assert isinstance(vision_llm, FakeVisionLLM)


def test_vision_llm_factory_accepts_bytes_image_input() -> None:
    settings = _settings_with_vision(provider="fake-vision")
    LLMFactory.register_vision_provider("fake-vision", FakeVisionLLM)
    vision_llm = LLMFactory.create_vision_llm(settings)

    assert vision_llm.chat_with_image("describe", b"encoded-image") == "fake-vision:fake-vision-model:bytes"


def test_vision_llm_preprocess_hook_supports_path_inputs() -> None:
    vision_llm = FakeVisionLLM(ProviderModelSettings(provider="fake-vision", model="fake-model"))

    assert vision_llm.preprocess_image(Path("image.png")) == "image.png"


def test_vision_llm_factory_rejects_missing_settings() -> None:
    settings = _settings_without_vision()

    with pytest.raises(ValueError, match="Vision LLM settings are not configured"):
        LLMFactory.create_vision_llm(settings)


def test_vision_llm_factory_rejects_unknown_provider() -> None:
    settings = _settings_with_vision(provider="missing")

    with pytest.raises(ValueError, match="Unsupported Vision LLM provider: missing"):
        LLMFactory.create_vision_llm(settings)


def test_vision_llm_factory_rejects_empty_provider_registration() -> None:
    with pytest.raises(ValueError, match="Vision LLM provider name must not be empty"):
        LLMFactory.register_vision_provider("  ", FakeVisionLLM)


def _settings_with_vision(
    provider: str,
    model: str | None = "fake-vision-model",
    max_image_size: int | None = None,
) -> Settings:
    settings = _settings_without_vision()
    return Settings(
        llm=settings.llm,
        embedding=settings.embedding,
        splitter=settings.splitter,
        vector_store=settings.vector_store,
        retrieval=settings.retrieval,
        rerank=settings.rerank,
        evaluation=settings.evaluation,
        observability=settings.observability,
        vision_llm=ProviderModelSettings(provider=provider, model=model, max_image_size=max_image_size),
        dashboard=settings.dashboard,
    )


def _settings_without_vision() -> Settings:
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
    )