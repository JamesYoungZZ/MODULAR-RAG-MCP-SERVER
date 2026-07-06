"""Base vector store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any


VectorRecord = Mapping[str, Any]
VectorQueryResult = Mapping[str, Any]


class BaseVectorStore(ABC):
    """Abstract interface for vector storage backends."""

    @abstractmethod
    def upsert(self, records: Sequence[VectorRecord], trace: Any | None = None) -> int:
        """Insert or update vector records and return the number of written records."""

    @abstractmethod
    def query(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
        trace: Any | None = None,
    ) -> list[VectorQueryResult]:
        """Return the top matching records for a query vector."""


__all__ = ["BaseVectorStore", "VectorQueryResult", "VectorRecord"]