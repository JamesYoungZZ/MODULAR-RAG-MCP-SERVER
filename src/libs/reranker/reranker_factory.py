"""Factory for reranker backends."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import RerankSettings, Settings

from libs.reranker.base_reranker import BaseReranker, NoneReranker


RerankerBuilder = Callable[[RerankSettings], BaseReranker]


class RerankerFactory:
    """Create rerankers from settings using a backend registry."""

    _backends: dict[str, RerankerBuilder] = {"none": NoneReranker}

    @classmethod
    def register_backend(cls, backend: str, builder: RerankerBuilder) -> None:
        backend_key = _normalize_backend(backend)
        if not backend_key:
            raise ValueError("Reranker backend name must not be empty")
        cls._backends[backend_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> BaseReranker:
        backend_key = _normalize_backend(settings.rerank.backend)
        if backend_key not in cls._backends:
            available = ", ".join(sorted(cls._backends)) or "none"
            raise ValueError(f"Unsupported reranker backend: {settings.rerank.backend}. Available backends: {available}")
        return cls._backends[backend_key](settings.rerank)


def _normalize_backend(backend: str) -> str:
    return backend.strip().lower()


__all__ = ["RerankerBuilder", "RerankerFactory"]