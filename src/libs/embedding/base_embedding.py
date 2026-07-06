"""Base embedding interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseEmbedding(ABC):
    """Abstract interface for text embedding clients."""

    @abstractmethod
    def embed(self, texts: list[str], trace: Any | None = None) -> list[list[float]]:
        """Return one embedding vector for each input text."""


__all__ = ["BaseEmbedding"]