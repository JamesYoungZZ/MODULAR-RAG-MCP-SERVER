"""Factory for embedding providers."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import ProviderModelSettings, Settings

from libs.embedding.base_embedding import BaseEmbedding


ProviderBuilder = Callable[[ProviderModelSettings], BaseEmbedding]


class EmbeddingFactory:
    """Create embedding clients from settings using a provider registry."""

    _providers: dict[str, ProviderBuilder] = {}

    @classmethod
    def register_provider(cls, provider: str, builder: ProviderBuilder) -> None:
        provider_key = _normalize_provider(provider)
        if not provider_key:
            raise ValueError("Embedding provider name must not be empty")
        cls._providers[provider_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> BaseEmbedding:
        provider_key = _normalize_provider(settings.embedding.provider)
        if provider_key not in cls._providers:
            available = ", ".join(sorted(cls._providers)) or "none"
            raise ValueError(
                f"Unsupported embedding provider: {settings.embedding.provider}. Available providers: {available}"
            )
        return cls._providers[provider_key](settings.embedding)


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


__all__ = ["EmbeddingFactory", "ProviderBuilder"]