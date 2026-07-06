"""Lightweight custom retrieval evaluator."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from libs.evaluator.base_evaluator import BaseEvaluator, EvaluationMetrics


class CustomEvaluator(BaseEvaluator):
    """Compute deterministic retrieval metrics without external dependencies."""

    def evaluate(
        self,
        query: str,
        retrieved_ids: Sequence[str],
        golden_ids: Sequence[str],
        trace: Any | None = None,
    ) -> EvaluationMetrics:
        golden_id_set = set(golden_ids)
        first_hit_rank = _first_hit_rank(retrieved_ids, golden_id_set)
        return {
            "hit_rate": 1.0 if first_hit_rank is not None else 0.0,
            "mrr": 1.0 / first_hit_rank if first_hit_rank is not None else 0.0,
        }


def _first_hit_rank(retrieved_ids: Sequence[str], golden_ids: set[str]) -> int | None:
    if not golden_ids:
        return None
    for index, retrieved_id in enumerate(retrieved_ids, start=1):
        if retrieved_id in golden_ids:
            return index
    return None


__all__ = ["CustomEvaluator"]