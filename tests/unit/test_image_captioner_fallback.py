from pathlib import Path
from typing import Any

from core import Chunk
from ingestion.transform import ImageCaptioner
from libs.llm import BaseVisionLLM, ImageInput


class FakeVisionLLM(BaseVisionLLM):
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, ImageInput]] = []

    def chat_with_image(self, text: str, image_path: ImageInput, trace: Any | None = None) -> str:
        self.calls.append((text, image_path))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_image_captioner_generates_captions_for_referenced_images() -> None:
    vision_llm = FakeVisionLLM("A chart showing retrieval accuracy by method.")
    chunk = _chunk()

    captioned = ImageCaptioner(vision_llm=vision_llm, prompt_template="Caption this image.").transform_chunk(chunk)

    assert captioned.id == chunk.id
    assert captioned.text == chunk.text
    assert captioned.start_offset == chunk.start_offset
    assert captioned.end_offset == chunk.end_offset
    assert captioned.source_ref == chunk.source_ref
    assert captioned.metadata["image_refs"] == ["img-1"]
    assert captioned.metadata["images"][0]["caption"] == "A chart showing retrieval accuracy by method."
    assert captioned.metadata["image_captions"] == {"img-1": "A chart showing retrieval accuracy by method."}
    assert captioned.metadata["has_unprocessed_images"] is False
    assert captioned.metadata["image_captioning_method"] == "vision_llm"
    prompt, image_path = vision_llm.calls[0]
    assert "Caption this image." in prompt
    assert "Chunk id: chunk-1" in prompt
    assert "Image id: img-1" in prompt
    assert image_path == "data/images/img-1.png"
    assert "caption" not in chunk.metadata["images"][0]


def test_image_captioner_preserves_chunks_without_image_refs() -> None:
    vision_llm = FakeVisionLLM("unused")
    chunk = Chunk(id="chunk-1", text="No images here", metadata={"source_path": "docs/a.pdf"})

    captioned = ImageCaptioner(vision_llm=vision_llm).transform_chunk(chunk)

    assert captioned is chunk
    assert vision_llm.calls == []


def test_image_captioner_disabled_marks_unprocessed_images() -> None:
    chunk = _chunk()

    captioned = ImageCaptioner().transform_chunk(chunk)

    assert captioned.metadata["image_refs"] == ["img-1"]
    assert "caption" not in captioned.metadata["images"][0]
    assert "image_captions" not in captioned.metadata
    assert captioned.metadata["has_unprocessed_images"] is True
    assert captioned.metadata["image_captioning_method"] == "disabled"


def test_image_captioner_falls_back_when_vision_llm_fails() -> None:
    chunk = _chunk()

    captioned = ImageCaptioner(vision_llm=FakeVisionLLM(RuntimeError("vision unavailable"))).transform_chunk(chunk)

    assert captioned.metadata["image_refs"] == ["img-1"]
    assert "caption" not in captioned.metadata["images"][0]
    assert captioned.metadata["has_unprocessed_images"] is True
    assert captioned.metadata["image_captioning_method"] == "fallback"
    assert captioned.metadata["image_captioning_error"] == "vision unavailable"


def test_image_captioner_falls_back_when_image_metadata_is_missing() -> None:
    chunk = Chunk(
        id="chunk-1",
        text="See [IMAGE: img-1]",
        metadata={"source_path": "docs/a.pdf", "image_refs": ["img-1"], "images": []},
    )

    captioned = ImageCaptioner(vision_llm=FakeVisionLLM("caption")).transform_chunk(chunk)

    assert captioned.metadata["has_unprocessed_images"] is True
    assert captioned.metadata["image_captioning_method"] == "fallback"
    assert captioned.metadata["image_captioning_error"] == "image metadata not found for ref: img-1"


def test_image_captioner_reads_prompt_from_path(tmp_path: Path) -> None:
    prompt_path = tmp_path / "image_captioning.txt"
    prompt_path.write_text("Custom image prompt", encoding="utf-8")
    vision_llm = FakeVisionLLM("caption")

    ImageCaptioner(vision_llm=vision_llm, prompt_path=prompt_path).transform_chunk(_chunk())

    assert "Custom image prompt" in vision_llm.calls[0][0]


def _chunk() -> Chunk:
    return Chunk(
        id="chunk-1",
        text="See [IMAGE: img-1] for a chart about retrieval accuracy.",
        metadata={
            "source_path": "docs/a.pdf",
            "image_refs": ["img-1"],
            "images": [_image("img-1")],
        },
        start_offset=3,
        end_offset=60,
        source_ref="doc-1",
    )


def _image(image_id: str) -> dict[str, object]:
    return {
        "id": image_id,
        "path": f"data/images/{image_id}.png",
        "page": 1,
        "text_offset": 4,
        "text_length": len(f"[IMAGE: {image_id}]"),
        "position": {},
    }