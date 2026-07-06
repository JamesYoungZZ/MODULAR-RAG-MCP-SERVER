"""LLM-based reranker implementation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from core.settings import RerankSettings

from libs.llm.base_llm import BaseLLM
from libs.reranker.base_reranker import BaseReranker, RerankCandidate


DEFAULT_RERANK_PROMPT_PATH = Path("config/prompts/rerank.txt")


class LLMRerankError(RuntimeError):
    """Raised when LLM reranking cannot produce a valid ranked id list."""

    def __init__(self, message: str, fallback_candidates: Sequence[RerankCandidate]) -> None:
        super().__init__(message)
        self.fallback_candidates = list(fallback_candidates)


class LLMReranker(BaseReranker):
    """Reranker that asks an LLM to return strict JSON ranked candidate ids."""

    def __init__(
        self,
        config: RerankSettings,
        llm: BaseLLM | None = None,
        prompt_template: str | None = None,
        prompt_path: str | Path = DEFAULT_RERANK_PROMPT_PATH,
    ) -> None:
        self.config = config
        self.llm = llm
        self.prompt_template = prompt_template if prompt_template is not None else self._load_prompt(prompt_path)

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        trace: Any | None = None,
    ) -> list[RerankCandidate]:
        candidate_list = list(candidates)
        if not candidate_list:
            return []
        if self.llm is None:
            raise LLMRerankError("llm reranker requires an LLM client", candidate_list)

        limited_candidates = candidate_list[: self.config.top_m] if self.config.top_m else candidate_list
        prompt = self._build_prompt(query, limited_candidates)
        response = self.llm.chat([{"role": "user", "content": prompt}])
        ranked_ids = self._parse_ranked_ids(response, limited_candidates)
        ranked_by_id = {str(candidate["id"]): candidate for candidate in limited_candidates}
        ranked_candidates = [ranked_by_id[candidate_id] for candidate_id in ranked_ids]

        remaining_candidates = [candidate for candidate in candidate_list if str(candidate.get("id")) not in ranked_ids]
        return ranked_candidates + remaining_candidates

    def _build_prompt(self, query: str, candidates: Sequence[RerankCandidate]) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("llm reranker query must be a non-empty string")
        payload = {
            "query": query,
            "candidates": [self._candidate_payload(candidate, index) for index, candidate in enumerate(candidates)],
        }
        return (
            f"{self.prompt_template.strip()}\n\n"
            "Return only JSON with this exact schema: {\"ranked_ids\": [\"candidate-id\"]}.\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _candidate_payload(self, candidate: RerankCandidate, index: int) -> dict[str, Any]:
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError(f"llm reranker candidates[{index}].id must be a non-empty string")
        return {
            "id": candidate_id,
            "text": candidate.get("text", ""),
            "metadata": candidate.get("metadata", {}),
            "score": candidate.get("score"),
        }

    def _parse_ranked_ids(self, response: str, candidates: Sequence[RerankCandidate]) -> list[str]:
        try:
            payload = json.loads(response)
            ranked_ids = payload["ranked_ids"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise LLMRerankError("llm reranker response must be JSON with ranked_ids", candidates) from exc

        if not isinstance(ranked_ids, list) or not all(isinstance(candidate_id, str) for candidate_id in ranked_ids):
            raise LLMRerankError("llm reranker ranked_ids must be a list of strings", candidates)

        expected_ids = {str(candidate["id"]) for candidate in candidates}
        ranked_id_set = set(ranked_ids)
        if ranked_id_set != expected_ids or len(ranked_ids) != len(expected_ids):
            raise LLMRerankError("llm reranker ranked_ids must contain each candidate id exactly once", candidates)
        return ranked_ids

    def _load_prompt(self, prompt_path: str | Path) -> str:
        try:
            prompt = Path(prompt_path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise LLMRerankError(f"llm reranker prompt not found: {prompt_path}", []) from exc
        if not prompt.strip():
            raise LLMRerankError(f"llm reranker prompt is empty: {prompt_path}", [])
        return prompt


__all__ = ["DEFAULT_RERANK_PROMPT_PATH", "LLMRerankError", "LLMReranker"]