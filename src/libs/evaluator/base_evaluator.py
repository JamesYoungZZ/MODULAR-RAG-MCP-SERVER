"""Base evaluator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


EvaluationMetrics = dict[str, float]


class BaseEvaluator(ABC):
    """Abstract interface for retrieval quality evaluators."""

    @abstractmethod
    def evaluate(
        self,
        query: str,
        retrieved_ids: Sequence[str],
        golden_ids: Sequence[str],
        trace: Any | None = None,
    ) -> EvaluationMetrics:
        """Return quality metrics for retrieved IDs against golden IDs."""


__all__ = ["BaseEvaluator", "EvaluationMetrics"]