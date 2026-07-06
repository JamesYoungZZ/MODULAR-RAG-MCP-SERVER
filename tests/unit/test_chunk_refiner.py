from collections.abc import Mapping, Sequence

import pytest

from core import Chunk
from ingestion.transform import BaseTransform, ChunkRefinementError, ChunkRefiner
from libs.llm import BaseLLM


class FakeLLM(BaseLLM):
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[Sequence[Mapping[str, str]]] = []

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        self.messages.append(messages)
        return self.response


class UppercaseTransform(BaseTransform):
    def transform_chunk(self, chunk: Chunk, trace: object | None = None) -> Chunk:
        return Chunk(
            id=chunk.id,
            text=chunk.text.upper(),
            metadata=dict(chunk.metadata),
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            source_ref=chunk.source_ref,
        )


def test_base_transform_transforms_chunks_in_order() -> None:
    chunks = [_chunk("chunk-1", "alpha"), _chunk("chunk-2", "beta")]

    transformed = UppercaseTransform().transform_chunks(chunks)

    assert [chunk.text for chunk in transformed] == ["ALPHA", "BETA"]
    assert [chunk.id for chunk in transformed] == ["chunk-1", "chunk-2"]


def test_chunk_refiner_calls_llm_and_preserves_chunk_identity() -> None:
    llm = FakeLLM("Refined text with enough context.")
    refiner = ChunkRefiner(llm=llm, prompt_template="Clean the chunk.")
    chunk = _chunk("chunk-1", "Noisy text", metadata={"source_path": "docs/a.pdf", "chunk_index": 0})

    refined = refiner.transform_chunk(chunk)

    assert refined.text == "Refined text with enough context."
    assert refined.id == chunk.id
    assert refined.start_offset == chunk.start_offset
    assert refined.end_offset == chunk.end_offset
    assert refined.source_ref == chunk.source_ref
    assert refined.metadata == {"source_path": "docs/a.pdf", "chunk_index": 0, "refined": True}
    assert chunk.text == "Noisy text"
    prompt = llm.messages[0][0]["content"]
    assert "Clean the chunk." in prompt
    assert '"id": "chunk-1"' in prompt
    assert '"source_path": "docs/a.pdf"' in prompt


def test_chunk_refiner_transforms_multiple_chunks_in_order() -> None:
    llm = FakeLLM("same refined text")
    refiner = ChunkRefiner(llm=llm, prompt_template="Clean.")

    refined = refiner.transform_chunks([_chunk("chunk-1", "alpha"), _chunk("chunk-2", "beta")])

    assert [chunk.id for chunk in refined] == ["chunk-1", "chunk-2"]
    assert [chunk.text for chunk in refined] == ["same refined text", "same refined text"]
    assert len(llm.messages) == 2


def test_chunk_refiner_rejects_empty_llm_response() -> None:
    refiner = ChunkRefiner(llm=FakeLLM("  "), prompt_template="Clean.")

    with pytest.raises(ChunkRefinementError, match="returned empty text"):
        refiner.transform_chunk(_chunk("chunk-1", "alpha"))


def test_chunk_refiner_reads_prompt_from_path(tmp_path) -> None:
    prompt_path = tmp_path / "chunk_refinement.txt"
    prompt_path.write_text("Custom refinement prompt", encoding="utf-8")

    refiner = ChunkRefiner(llm=FakeLLM("refined"), prompt_path=prompt_path)

    assert refiner.prompt_template == "Custom refinement prompt"


def test_chunk_refiner_requires_settings_or_llm() -> None:
    with pytest.raises(ChunkRefinementError, match="requires either settings or an LLM client"):
        ChunkRefiner(prompt_template="Clean.")


def _chunk(chunk_id: str, text: str, metadata: dict[str, object] | None = None) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=metadata or {"source_path": "docs/a.pdf"},
        start_offset=2,
        end_offset=2 + len(text),
        source_ref="doc-1",
    )