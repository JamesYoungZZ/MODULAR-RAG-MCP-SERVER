"""Chunk metadata enrichment transform."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core import Chunk
from core.settings import Settings
from libs.llm import BaseLLM, LLMFactory

from ingestion.transform.base_transform import BaseTransform


DEFAULT_METADATA_PROMPT = """Generate retrieval metadata for this chunk."""
MAX_TITLE_LENGTH = 80
MAX_SUMMARY_LENGTH = 240
TAG_LIMIT = 5
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+")
STOPWORDS = {
    "and",
    "are",
    "but",
    "for",
    "from",
    "into",
    "not",
    "that",
    "the",
    "this",
    "with",
}


class MetadataEnricher(BaseTransform):
    """Add title, summary, and tags metadata to chunks."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: BaseLLM | None = None,
        prompt_template: str = DEFAULT_METADATA_PROMPT,
    ) -> None:
        self.llm = llm or (LLMFactory.create(settings) if settings is not None else None)
        self.prompt_template = prompt_template

    def transform_chunk(self, chunk: Chunk, trace: Any | None = None) -> Chunk:
        fallback_metadata = _rule_metadata(chunk)
        metadata = dict(chunk.metadata)

        if self.llm is None:
            enriched_metadata = fallback_metadata
            method = "rule"
        else:
            try:
                enriched_metadata = _normalize_enrichment(self._generate_metadata(chunk), fallback_metadata)
                method = "llm"
            except Exception as exc:
                enriched_metadata = fallback_metadata
                method = "rule_fallback"
                metadata["metadata_enrichment_fallback_reason"] = str(exc)

        metadata.update(enriched_metadata)
        metadata["metadata_enriched"] = True
        metadata["metadata_enrichment_method"] = method
        return Chunk(
            id=chunk.id,
            text=chunk.text,
            metadata=metadata,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            source_ref=chunk.source_ref,
        )

    def _generate_metadata(self, chunk: Chunk) -> dict[str, Any]:
        response = self.llm.chat([{"role": "user", "content": self._build_prompt(chunk)}])  # type: ignore[union-attr]
        payload = json.loads(response)
        if not isinstance(payload, dict):
            raise ValueError("metadata enrichment response must be a JSON object")
        return payload

    def _build_prompt(self, chunk: Chunk) -> str:
        payload = {
            "id": chunk.id,
            "text": chunk.text,
            "metadata": chunk.metadata,
            "source_ref": chunk.source_ref,
        }
        return (
            f"{self.prompt_template.strip()}\n\n"
            "Return only JSON with this exact schema: "
            '{"title": "short title", "summary": "one or two sentence summary", "tags": ["tag"]}.\n'
            f"Chunk:\n{json.dumps(payload, ensure_ascii=False)}"
        )


def _rule_metadata(chunk: Chunk) -> dict[str, Any]:
    title = _existing_string(chunk.metadata.get("title")) or _title_from_text(chunk.text) or _title_from_source(chunk)
    summary = _existing_string(chunk.metadata.get("summary")) or _summary_from_text(chunk.text) or title
    tags = _existing_tags(chunk.metadata.get("tags")) or _tags_from_chunk(chunk) or ["chunk"]
    return {"title": title, "summary": summary, "tags": tags}


def _normalize_enrichment(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    title = _existing_string(payload.get("title")) or fallback["title"]
    summary = _existing_string(payload.get("summary")) or fallback["summary"]
    tags = _existing_tags(payload.get("tags")) or fallback["tags"]
    return {"title": title, "summary": summary, "tags": tags}


def _title_from_text(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = MARKDOWN_HEADING_PATTERN.sub("", raw_line.strip()).strip(" -*_`")
        if line:
            return _truncate(line, MAX_TITLE_LENGTH)
    return None


def _title_from_source(chunk: Chunk) -> str:
    source_path = chunk.metadata.get("source_path")
    if isinstance(source_path, str) and source_path.strip():
        return _truncate(Path(source_path).stem.replace("_", " ").replace("-", " ").title(), MAX_TITLE_LENGTH)
    return _truncate(chunk.id, MAX_TITLE_LENGTH)


def _summary_from_text(text: str) -> str | None:
    normalized = " ".join(text.split())
    if not normalized:
        return None
    return _truncate(normalized, MAX_SUMMARY_LENGTH)


def _tags_from_chunk(chunk: Chunk) -> list[str]:
    tags: list[str] = []
    doc_type = chunk.metadata.get("doc_type")
    if isinstance(doc_type, str) and doc_type.strip():
        tags.append(doc_type.strip().lower())

    for token in TOKEN_PATTERN.findall(chunk.text.lower()):
        if token not in STOPWORDS and token not in tags:
            tags.append(token)
        if len(tags) >= TAG_LIMIT:
            break
    return tags


def _existing_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _existing_tags(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    tags = [tag.strip() for tag in value if isinstance(tag, str) and tag.strip()]
    return tags or None


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."


__all__ = ["MetadataEnricher"]