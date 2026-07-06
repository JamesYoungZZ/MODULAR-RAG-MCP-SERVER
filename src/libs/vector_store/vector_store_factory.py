"""Factory for vector store backends."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import Settings, VectorStoreSettings

from libs.vector_store.base_vector_store import BaseVectorStore


VectorStoreBuilder = Callable[[VectorStoreSettings], BaseVectorStore]


class VectorStoreFactory:
    """Create vector stores from settings using a backend registry."""

    _backends: dict[str, VectorStoreBuilder] = {}

    @classmethod
    def register_backend(cls, backend: str, builder: VectorStoreBuilder) -> None:
        backend_key = _normalize_backend(backend)
        if not backend_key:
            raise ValueError("Vector store backend name must not be empty")
        cls._backends[backend_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> BaseVectorStore:
        backend_key = _normalize_backend(settings.vector_store.backend)
        if backend_key not in cls._backends:
            available = ", ".join(sorted(cls._backends)) or "none"
            raise ValueError(
                f"Unsupported vector store backend: {settings.vector_store.backend}. Available backends: {available}"
            )
        return cls._backends[backend_key](settings.vector_store)


def _normalize_backend(backend: str) -> str:
    return backend.strip().lower()


__all__ = ["VectorStoreBuilder", "VectorStoreFactory"]