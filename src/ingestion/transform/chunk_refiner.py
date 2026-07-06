"""LLM-backed chunk refinement transform."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core import Chunk
from core.settings import Settings
from libs.llm import BaseLLM, LLMFactory

from ingestion.transform.base_transform import BaseTransform


DEFAULT_CHUNK_REFINEMENT_PROMPT_PATH = Path("config/prompts/chunk_refinement.txt")


class ChunkRefinementError(RuntimeError):
    """Raised when chunk refinement cannot produce valid text."""


class ChunkRefiner(BaseTransform):
    """Refine split chunks into cleaner, self-contained text using an LLM."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: BaseLLM | None = None,
        prompt_template: str | None = None,
        prompt_path: str | Path = DEFAULT_CHUNK_REFINEMENT_PROMPT_PATH,
    ) -> None:
        if llm is None and settings is None:
            raise ChunkRefinementError("chunk refiner requires either settings or an LLM client")
        self.llm = llm or LLMFactory.create(settings)  # type: ignore[arg-type]
        self.prompt_template = prompt_template if prompt_template is not None else self._load_prompt(prompt_path)

    def transform_chunk(self, chunk: Chunk, trace: Any | None = None) -> Chunk:
        prompt = self._build_prompt(chunk)
        refined_text = self.llm.chat([{"role": "user", "content": prompt}]).strip()
        if not refined_text:
            raise ChunkRefinementError(f"chunk refiner returned empty text for chunk: {chunk.id}")

        metadata = dict(chunk.metadata)
        metadata["refined"] = True
        return Chunk(
            id=chunk.id,
            text=refined_text,
            metadata=metadata,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            source_ref=chunk.source_ref,
        )

    def _build_prompt(self, chunk: Chunk) -> str:
        payload = {
            "id": chunk.id,
            "text": chunk.text,
            "metadata": chunk.metadata,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "source_ref": chunk.source_ref,
        }
        return (
            f"{self.prompt_template.strip()}\n\n"
            "Refine the chunk into clean, self-contained retrieval text. "
            "Return only the refined chunk text, with no JSON or explanation.\n"
            f"Chunk:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _load_prompt(self, prompt_path: str | Path) -> str:
        try:
            prompt = Path(prompt_path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ChunkRefinementError(f"chunk refinement prompt not found: {prompt_path}") from exc
        if not prompt.strip():
            raise ChunkRefinementError(f"chunk refinement prompt is empty: {prompt_path}")
        return prompt


__all__ = ["ChunkRefinementError", "ChunkRefiner", "DEFAULT_CHUNK_REFINEMENT_PROMPT_PATH"]