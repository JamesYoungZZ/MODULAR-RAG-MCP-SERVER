"""PDF loader implementation for ingestion."""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import Document
from libs.loader.base_loader import BaseLoader
from observability.logger import get_logger


PdfConverter = Callable[[Path], str]
ImageExtractor = Callable[[Path, str, Path], list[dict[str, Any]]]


class PdfLoader(BaseLoader):
    """Load PDFs into canonical Markdown-like Document objects."""

    def __init__(
        self,
        converter: PdfConverter | None = None,
        image_extractor: ImageExtractor | None = None,
        image_output_root: str | Path = "data/images",
    ) -> None:
        self._converter = converter or _convert_pdf_to_markdown
        self._image_extractor = image_extractor or _extract_no_images
        self._image_output_root = Path(image_output_root)
        self._logger = get_logger(__name__)

    def load(self, path: str | Path) -> Document:
        pdf_path = Path(path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"PdfLoader only supports .pdf files: {pdf_path}")

        doc_hash = self._compute_doc_hash(pdf_path)
        text = self._converter(pdf_path).strip()
        if not text:
            text = f"# {pdf_path.stem}"

        images = self._safe_extract_images(pdf_path, doc_hash)
        text, images = _ensure_image_placeholders(text, images)
        metadata: dict[str, Any] = {
            "source_path": str(pdf_path),
            "doc_type": "pdf",
            "file_hash": doc_hash,
            "images": images,
        }
        return Document(id=doc_hash, text=text, metadata=metadata)

    def _compute_doc_hash(self, pdf_path: Path) -> str:
        digest = hashlib.sha256()
        with pdf_path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _safe_extract_images(self, pdf_path: Path, doc_hash: str) -> list[dict[str, Any]]:
        output_dir = self._image_output_root / doc_hash
        try:
            raw_images = self._image_extractor(pdf_path, doc_hash, output_dir)
        except Exception as exc:  # noqa: BLE001 - image extraction must not block text loading.
            self._logger.warning("PDF image extraction failed for %s: %s", pdf_path, exc)
            return []
        return [_normalize_image_metadata(image, doc_hash, output_dir, index) for index, image in enumerate(raw_images)]


def _convert_pdf_to_markdown(pdf_path: Path) -> str:
    try:
        from markitdown import MarkItDown  # type: ignore[import-not-found]
    except ImportError:
        return _extract_pdf_text_literals(pdf_path)

    result = MarkItDown().convert(str(pdf_path))
    text_content = getattr(result, "text_content", None)
    if not isinstance(text_content, str):
        raise ValueError("MarkItDown did not return text_content")
    return text_content


def _extract_pdf_text_literals(pdf_path: Path) -> str:
    raw_text = pdf_path.read_bytes().decode("latin-1", errors="ignore")
    literals = [_unescape_pdf_literal(match) for match in re.findall(r"\((.*?)\)\s*Tj", raw_text, flags=re.DOTALL)]
    if literals:
        return "\n".join(literal for literal in literals if literal.strip())
    return raw_text.strip()


def _unescape_pdf_literal(value: str) -> str:
    return value.replace(r"\(", "(").replace(r"\)", ")").replace(r"\n", "\n")


def _extract_no_images(pdf_path: Path, doc_hash: str, output_dir: Path) -> list[dict[str, Any]]:
    return []


def _ensure_image_placeholders(text: str, images: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    updated_text = text
    normalized_images: list[dict[str, Any]] = []
    for image in images:
        image_id = image["id"]
        placeholder = f"[IMAGE: {image_id}]"
        if placeholder in updated_text:
            text_offset = updated_text.index(placeholder)
        elif "text_offset" in image and isinstance(image["text_offset"], int) and updated_text[image["text_offset"] : image["text_offset"] + len(placeholder)] == placeholder:
            text_offset = image["text_offset"]
        else:
            separator = "\n" if updated_text else ""
            text_offset = len(updated_text) + len(separator)
            updated_text = f"{updated_text}{separator}{placeholder}"
        normalized_image = dict(image)
        normalized_image["text_offset"] = text_offset
        normalized_image["text_length"] = len(placeholder)
        normalized_images.append(normalized_image)
    return updated_text, normalized_images


def _normalize_image_metadata(image: dict[str, Any], doc_hash: str, output_dir: Path, index: int) -> dict[str, Any]:
    image_id = _string_value(image.get("id"), f"{doc_hash}_1_{index + 1}")
    page = image.get("page", 1)
    image_path = _store_image_path(image.get("path"), image_id, output_dir)
    return {
        "id": image_id,
        "path": str(image_path),
        "page": page,
        "text_offset": image.get("text_offset", 0),
        "text_length": image.get("text_length", len(f"[IMAGE: {image_id}]")),
        "position": image.get("position", {}),
    }


def _store_image_path(path_value: Any, image_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / f"{image_id}.png"
    if isinstance(path_value, str) and path_value.strip():
        source_path = Path(path_value)
        if source_path.exists() and source_path.resolve() != target_path.resolve():
            shutil.copyfile(source_path, target_path)
            return target_path
        return source_path
    return target_path


def _string_value(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


__all__ = ["ImageExtractor", "PdfConverter", "PdfLoader"]