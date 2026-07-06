"""Shared data contracts used across ingestion, retrieval, and MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Metadata = dict[str, Any]
DenseVector = list[float]
SparseVector = dict[str, float]


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.id, "document.id")
        _validate_text(self.text, "document.text")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: Metadata = field(default_factory=dict)
    start_offset: int = 0
    end_offset: int = 0
    source_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id, "chunk.id")
        _validate_text(self.text, "chunk.text")
        _validate_metadata(self.metadata)
        _validate_offsets(self.start_offset, self.end_offset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": dict(self.metadata),
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    text: str
    metadata: Metadata = field(default_factory=dict)
    dense_vector: DenseVector | None = None
    sparse_vector: SparseVector | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id, "chunk_record.id")
        _validate_text(self.text, "chunk_record.text")
        _validate_metadata(self.metadata)
        if self.dense_vector is not None:
            _validate_dense_vector(self.dense_vector)
        if self.sparse_vector is not None:
            _validate_sparse_vector(self.sparse_vector)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": dict(self.metadata),
            "dense_vector": list(self.dense_vector) if self.dense_vector is not None else None,
            "sparse_vector": dict(self.sparse_vector) if self.sparse_vector is not None else None,
        }

    def to_vector_record(self) -> dict[str, Any]:
        if self.dense_vector is None:
            raise ValueError("chunk_record.dense_vector is required for vector upsert")
        return {"id": self.id, "text": self.text, "metadata": dict(self.metadata), "vector": list(self.dense_vector)}


def _validate_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")


def _validate_metadata(metadata: Metadata) -> None:
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a mapping")
    source_path = metadata.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("metadata.source_path must be a non-empty string")
    images = metadata.get("images", [])
    if images is None:
        return
    if not isinstance(images, list):
        raise ValueError("metadata.images must be a list")
    for index, image in enumerate(images):
        _validate_image_metadata(image, index)


def _validate_image_metadata(image: Any, index: int) -> None:
    if not isinstance(image, dict):
        raise ValueError(f"metadata.images[{index}] must be a mapping")
    for field_name in ("id", "path"):
        value = image.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"metadata.images[{index}].{field_name} must be a non-empty string")
    for field_name in ("text_offset", "text_length"):
        value = image.get(field_name)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"metadata.images[{index}].{field_name} must be a non-negative integer")
    if "page" in image and image["page"] is not None and (not isinstance(image["page"], int) or image["page"] < 1):
        raise ValueError(f"metadata.images[{index}].page must be a positive integer")
    if "position" in image and image["position"] is not None and not isinstance(image["position"], dict):
        raise ValueError(f"metadata.images[{index}].position must be a mapping")


def _validate_offsets(start_offset: int, end_offset: int) -> None:
    if not isinstance(start_offset, int) or start_offset < 0:
        raise ValueError("chunk.start_offset must be a non-negative integer")
    if not isinstance(end_offset, int) or end_offset < start_offset:
        raise ValueError("chunk.end_offset must be greater than or equal to start_offset")


def _validate_dense_vector(vector: DenseVector) -> None:
    if not isinstance(vector, list) or not all(isinstance(value, float) for value in vector):
        raise ValueError("chunk_record.dense_vector must be a list of floats")


def _validate_sparse_vector(vector: SparseVector) -> None:
    if not isinstance(vector, dict) or not all(isinstance(key, str) and isinstance(value, float) for key, value in vector.items()):
        raise ValueError("chunk_record.sparse_vector must map strings to floats")


__all__ = ["Chunk", "ChunkRecord", "DenseVector", "Document", "Metadata", "SparseVector"]