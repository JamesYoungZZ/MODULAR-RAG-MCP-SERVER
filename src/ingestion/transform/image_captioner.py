"""Vision LLM image captioning transform."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import Chunk
from core.settings import Settings
from libs.llm import BaseVisionLLM, LLMFactory

from ingestion.transform.base_transform import BaseTransform


DEFAULT_IMAGE_CAPTION_PROMPT_PATH = Path("config/prompts/image_captioning.txt")


class ImageCaptioner(BaseTransform):
    """Generate captions for chunk image references without blocking ingestion."""

    def __init__(
        self,
        settings: Settings | None = None,
        vision_llm: BaseVisionLLM | None = None,
        prompt_template: str | None = None,
        prompt_path: str | Path = DEFAULT_IMAGE_CAPTION_PROMPT_PATH,
    ) -> None:
        self.vision_llm = vision_llm or _create_optional_vision_llm(settings)
        self.prompt_template = prompt_template if prompt_template is not None else self._load_prompt(prompt_path)

    def transform_chunk(self, chunk: Chunk, trace: Any | None = None) -> Chunk:
        image_refs = _image_refs(chunk.metadata.get("image_refs"))
        if not image_refs:
            return chunk

        images = _images_by_ref(chunk.metadata.get("images"), image_refs)
        metadata = dict(chunk.metadata)
        if self.vision_llm is None:
            metadata["has_unprocessed_images"] = True
            metadata["image_captioning_method"] = "disabled"
            return _copy_chunk(chunk, metadata)

        try:
            captioned_images, captions = self._caption_images(chunk, image_refs, images, trace=trace)
        except Exception as exc:
            metadata["has_unprocessed_images"] = True
            metadata["image_captioning_method"] = "fallback"
            metadata["image_captioning_error"] = str(exc)
            return _copy_chunk(chunk, metadata)

        metadata["images"] = captioned_images
        metadata["image_captions"] = captions
        metadata["has_unprocessed_images"] = False
        metadata["image_captioning_method"] = "vision_llm"
        return _copy_chunk(chunk, metadata)

    def _caption_images(
        self,
        chunk: Chunk,
        image_refs: list[str],
        images: dict[str, dict[str, Any]],
        trace: Any | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        captioned_images: list[dict[str, Any]] = []
        captions: dict[str, str] = {}
        for image_ref in image_refs:
            image = images.get(image_ref)
            if image is None:
                raise ValueError(f"image metadata not found for ref: {image_ref}")
            image_path = image.get("path")
            if not isinstance(image_path, str) or not image_path.strip():
                raise ValueError(f"image path is missing for ref: {image_ref}")
            caption = self.vision_llm.chat_with_image(self._build_prompt(chunk, image), image_path, trace=trace)  # type: ignore[union-attr]
            caption = caption.strip()
            if not caption:
                raise ValueError(f"empty caption for ref: {image_ref}")
            captioned_image = dict(image)
            captioned_image["caption"] = caption
            captioned_images.append(captioned_image)
            captions[image_ref] = caption
        return captioned_images, captions

    def _build_prompt(self, chunk: Chunk, image: dict[str, Any]) -> str:
        return (
            f"{self.prompt_template.strip()}\n\n"
            "Describe the image for retrieval. Focus on visible text, chart/table structure, and concepts.\n"
            f"Chunk id: {chunk.id}\n"
            f"Image id: {image.get('id')}\n"
            f"Nearby chunk text:\n{chunk.text}"
        )

    def _load_prompt(self, prompt_path: str | Path) -> str:
        try:
            prompt = Path(prompt_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return "Describe this document image for retrieval."
        return prompt.strip() or "Describe this document image for retrieval."


def _create_optional_vision_llm(settings: Settings | None) -> BaseVisionLLM | None:
    if settings is None or settings.vision_llm is None:
        return None
    return LLMFactory.create_vision_llm(settings)


def _image_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in refs:
            refs.append(item.strip())
    return refs


def _images_by_ref(value: Any, image_refs: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    allowed_refs = set(image_refs)
    images: dict[str, dict[str, Any]] = {}
    for image in value:
        if not isinstance(image, dict):
            continue
        image_id = image.get("id")
        if isinstance(image_id, str) and image_id in allowed_refs:
            images[image_id] = dict(image)
    return images


def _copy_chunk(chunk: Chunk, metadata: dict[str, Any]) -> Chunk:
    return Chunk(
        id=chunk.id,
        text=chunk.text,
        metadata=metadata,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
        source_ref=chunk.source_ref,
    )


__all__ = ["DEFAULT_IMAGE_CAPTION_PROMPT_PATH", "ImageCaptioner"]