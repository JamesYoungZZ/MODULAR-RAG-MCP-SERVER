"""Cross-encoder reranker implementation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from core.settings import RerankSettings

from libs.reranker.base_reranker import BaseReranker, RerankCandidate


CrossEncoderScorer = Callable[[str, Sequence[RerankCandidate]], Sequence[float]]


class CrossEncoderRerankError(RuntimeError):
    """Raised when cross-encoder reranking cannot produce valid scores."""

    def __init__(self, message: str, fallback_candidates: Sequence[RerankCandidate]) -> None:
        super().__init__(message)
        self.fallback_candidates = list(fallback_candidates)


class CrossEncoderReranker(BaseReranker):
    """Reranker that scores query/candidate pairs with an injected scorer."""

    def __init__(self, config: RerankSettings, scorer: CrossEncoderScorer | None = None) -> None:
        self.config = config
        self.scorer = scorer

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        trace: Any | None = None,
    ) -> list[RerankCandidate]:
        candidate_list = list(candidates)
        if not candidate_list:
            return []
        if not isinstance(query, str) or not query.strip():
            raise ValueError("cross_encoder reranker query must be a non-empty string")
        for index, candidate in enumerate(candidate_list):
            self._validate_candidate(candidate, index)
        if self.scorer is None:
            raise CrossEncoderRerankError("cross_encoder reranker requires a scorer", candidate_list)

        limited_candidates = candidate_list[: self.config.top_m] if self.config.top_m else candidate_list
        try:
            scores = list(self.scorer(query, limited_candidates))
        except TimeoutError as exc:
            raise CrossEncoderRerankError("cross_encoder reranker scoring timed out", candidate_list) from exc
        except Exception as exc:
            raise CrossEncoderRerankError(
                f"cross_encoder reranker scoring failed: {exc.__class__.__name__}", candidate_list
            ) from exc

        if len(scores) != len(limited_candidates):
            raise CrossEncoderRerankError("cross_encoder scorer must return one score per candidate", candidate_list)
        if not all(isinstance(score, int | float) for score in scores):
            raise CrossEncoderRerankError("cross_encoder scorer scores must be numeric", candidate_list)

        scored_candidates = list(zip(limited_candidates, [float(score) for score in scores], strict=True))
        ranked_candidates = [
            candidate for candidate, _score in sorted(scored_candidates, key=lambda item: item[1], reverse=True)
        ]
        ranked_ids = {str(candidate["id"]) for candidate in ranked_candidates}
        remaining_candidates = [candidate for candidate in candidate_list if str(candidate.get("id")) not in ranked_ids]
        return ranked_candidates + remaining_candidates

    def _validate_candidate(self, candidate: RerankCandidate, index: int) -> None:
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError(f"cross_encoder reranker candidates[{index}].id must be a non-empty string")


__all__ = ["CrossEncoderRerankError", "CrossEncoderReranker", "CrossEncoderScorer"]