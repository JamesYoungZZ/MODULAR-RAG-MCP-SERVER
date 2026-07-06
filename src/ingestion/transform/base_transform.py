"""Base contract for ingestion chunk transforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from core import Chunk


class BaseTransform(ABC):
    """Abstract interface for Chunk -> Chunk enrichment steps."""

    @abstractmethod
    def transform_chunk(self, chunk: Chunk, trace: Any | None = None) -> Chunk:
        """Return a transformed Chunk without mutating the input chunk."""

    def transform_chunks(self, chunks: Sequence[Chunk], trace: Any | None = None) -> list[Chunk]:
        """Transform a sequence of chunks while preserving order."""
        return [self.transform_chunk(chunk, trace=trace) for chunk in chunks]


__all__ = ["BaseTransform"]