"""Adapt text splitters into Document -> Chunk conversion."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from core import Chunk, Document
from core.settings import Settings
from libs.splitter import BaseSplitter, SplitterFactory


IMAGE_PLACEHOLDER_PATTERN = re.compile(r"\[IMAGE:\s*([^\]]+)\]")


class DocumentChunker:
    """Split Document objects into typed Chunk objects with ingestion metadata."""

    def __init__(self, settings: Settings, splitter: BaseSplitter | None = None) -> None:
        self._splitter = splitter or SplitterFactory.create(settings)

    def split_document(self, document: Document) -> list[Chunk]:
        chunk_texts = self._splitter.split_text(document.text)
        chunks: list[Chunk] = []
        search_from = 0
        for index, chunk_text in enumerate(chunk_texts):
            start_offset = _find_chunk_offset(document.text, chunk_text, search_from)
            end_offset = start_offset + len(chunk_text)
            search_from = end_offset
            chunks.append(
                Chunk(
                    id=self._generate_chunk_id(document.id, index, chunk_text),
                    text=chunk_text,
                    metadata=self._inherit_metadata(document, index, chunk_text),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    source_ref=document.id,
                )
            )
        return chunks

    def _generate_chunk_id(self, doc_id: str, index: int, text: str) -> str:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        return f"{doc_id}_{index:04d}_{content_hash}"

    def _inherit_metadata(self, document: Document, chunk_index: int, chunk_text: str) -> dict[str, Any]:
        metadata = {key: value for key, value in document.metadata.items() if key != "images"}
        metadata["chunk_index"] = chunk_index

        referenced_image_ids = _extract_image_refs(chunk_text)
        if referenced_image_ids:
            images = _images_for_refs(document.metadata.get("images", []), referenced_image_ids)
            metadata["image_refs"] = referenced_image_ids
            metadata["images"] = images
        return metadata


def _find_chunk_offset(document_text: str, chunk_text: str, start: int) -> int:
    offset = document_text.find(chunk_text, start)
    if offset >= 0:
        return offset
    fallback_offset = document_text.find(chunk_text)
    if fallback_offset >= 0:
        return fallback_offset
    return start


def _extract_image_refs(chunk_text: str) -> list[str]:
    refs: list[str] = []
    for match in IMAGE_PLACEHOLDER_PATTERN.finditer(chunk_text):
        image_id = match.group(1).strip()
        if image_id and image_id not in refs:
            refs.append(image_id)
    return refs


def _images_for_refs(images: Any, image_refs: list[str]) -> list[dict[str, Any]]:
    if not isinstance(images, list):
        return []
    image_by_id = {image.get("id"): image for image in images if isinstance(image, dict)}
    return [dict(image_by_id[image_ref]) for image_ref in image_refs if image_ref in image_by_id]


__all__ = ["DocumentChunker", "IMAGE_PLACEHOLDER_PATTERN"]