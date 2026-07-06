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
        _register_builtin_backends(cls)
        backend_key = _normalize_backend(settings.rerank.backend)
        if backend_key not in cls._backends:
            available = ", ".join(sorted(cls._backends)) or "none"
            raise ValueError(f"Unsupported reranker backend: {settings.rerank.backend}. Available backends: {available}")
        return cls._backends[backend_key](settings.rerank)


def _normalize_backend(backend: str) -> str:
    return backend.strip().lower()


def _register_builtin_backends(factory: type[RerankerFactory]) -> None:
    from libs.reranker.cross_encoder_reranker import CrossEncoderReranker
    from libs.reranker.llm_reranker import LLMReranker

    builtin_backends: dict[str, RerankerBuilder] = {
        "cross_encoder": CrossEncoderReranker,
        "llm": LLMReranker,
    }
    for backend, builder in builtin_backends.items():
        factory._backends.setdefault(backend, builder)


__all__ = ["RerankerBuilder", "RerankerFactory"]