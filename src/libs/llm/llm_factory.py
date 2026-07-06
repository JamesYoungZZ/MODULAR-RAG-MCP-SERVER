"""Factory for LLM providers."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import ProviderModelSettings, Settings

from libs.llm.base_llm import BaseLLM


ProviderBuilder = Callable[[ProviderModelSettings], BaseLLM]


class LLMFactory:
    """Create LLM clients from settings using a provider registry."""

    _providers: dict[str, ProviderBuilder] = {}

    @classmethod
    def register_provider(cls, provider: str, builder: ProviderBuilder) -> None:
        provider_key = _normalize_provider(provider)
        if not provider_key:
            raise ValueError("LLM provider name must not be empty")
        cls._providers[provider_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> BaseLLM:
        _register_builtin_providers(cls)
        provider_key = _normalize_provider(settings.llm.provider)
        if provider_key not in cls._providers:
            available = ", ".join(sorted(cls._providers)) or "none"
            raise ValueError(f"Unsupported LLM provider: {settings.llm.provider}. Available providers: {available}")
        return cls._providers[provider_key](settings.llm)


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _register_builtin_providers(factory: type[LLMFactory]) -> None:
    from libs.llm.openai_llm import AzureOpenAILLM, DeepSeekLLM, OpenAICompatibleLLM

    builtin_providers: dict[str, ProviderBuilder] = {
        "openai": OpenAICompatibleLLM,
        "azure": AzureOpenAILLM,
        "deepseek": DeepSeekLLM,
    }
    for provider, builder in builtin_providers.items():
        factory._providers.setdefault(provider, builder)


__all__ = ["LLMFactory", "ProviderBuilder"]