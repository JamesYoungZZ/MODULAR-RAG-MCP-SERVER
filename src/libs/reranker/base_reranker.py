"""Base reranker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from core.settings import RerankSettings


RerankCandidate = Mapping[str, Any]


class BaseReranker(ABC):
    """Abstract interface for reranking retrieved candidates."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        trace: Any | None = None,
    ) -> list[RerankCandidate]:
        """Return candidates ordered by relevance to the query."""


class NoneReranker(BaseReranker):
    """Reranker implementation that keeps the input order unchanged."""

    def __init__(self, config: RerankSettings | None = None) -> None:
        self.config = config

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        trace: Any | None = None,
    ) -> list[RerankCandidate]:
        return list(candidates)


__all__ = ["BaseReranker", "NoneReranker", "RerankCandidate"]