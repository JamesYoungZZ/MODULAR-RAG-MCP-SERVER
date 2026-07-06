"""Factory for LLM providers."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import ProviderModelSettings, Settings

from libs.llm.base_llm import BaseLLM
from libs.llm.base_vision_llm import BaseVisionLLM


ProviderBuilder = Callable[[ProviderModelSettings], BaseLLM]
VisionProviderBuilder = Callable[[ProviderModelSettings], BaseVisionLLM]


class LLMFactory:
    """Create LLM clients from settings using a provider registry."""

    _providers: dict[str, ProviderBuilder] = {}
    _vision_providers: dict[str, VisionProviderBuilder] = {}

    @classmethod
    def register_provider(cls, provider: str, builder: ProviderBuilder) -> None:
        provider_key = _normalize_provider(provider)
        if not provider_key:
            raise ValueError("LLM provider name must not be empty")
        cls._providers[provider_key] = builder

    @classmethod
    def register_vision_provider(cls, provider: str, builder: VisionProviderBuilder) -> None:
        provider_key = _normalize_provider(provider)
        if not provider_key:
            raise ValueError("Vision LLM provider name must not be empty")
        cls._vision_providers[provider_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> BaseLLM:
        _register_builtin_providers(cls)
        provider_key = _normalize_provider(settings.llm.provider)
        if provider_key not in cls._providers:
            available = ", ".join(sorted(cls._providers)) or "none"
            raise ValueError(f"Unsupported LLM provider: {settings.llm.provider}. Available providers: {available}")
        return cls._providers[provider_key](settings.llm)

    @classmethod
    def create_vision_llm(cls, settings: Settings) -> BaseVisionLLM:
        if settings.vision_llm is None:
            raise ValueError("Vision LLM settings are not configured")
        _register_builtin_vision_providers(cls)
        provider_key = _normalize_provider(settings.vision_llm.provider)
        if provider_key not in cls._vision_providers:
            available = ", ".join(sorted(cls._vision_providers)) or "none"
            raise ValueError(
                f"Unsupported Vision LLM provider: {settings.vision_llm.provider}. Available providers: {available}"
            )
        return cls._vision_providers[provider_key](settings.vision_llm)


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _register_builtin_providers(factory: type[LLMFactory]) -> None:
    from libs.llm.openai_llm import AzureOpenAILLM, DeepSeekLLM, OpenAICompatibleLLM
    from libs.llm.ollama_llm import OllamaLLM

    builtin_providers: dict[str, ProviderBuilder] = {
        "openai": OpenAICompatibleLLM,
        "azure": AzureOpenAILLM,
        "deepseek": DeepSeekLLM,
        "ollama": OllamaLLM,
    }
    for provider, builder in builtin_providers.items():
        factory._providers.setdefault(provider, builder)


def _register_builtin_vision_providers(factory: type[LLMFactory]) -> None:
    from libs.llm.azure_vision_llm import AzureVisionLLM

    builtin_providers: dict[str, VisionProviderBuilder] = {
        "azure": AzureVisionLLM,
    }
    for provider, builder in builtin_providers.items():
        factory._vision_providers.setdefault(provider, builder)


__all__ = ["LLMFactory", "ProviderBuilder", "VisionProviderBuilder"]