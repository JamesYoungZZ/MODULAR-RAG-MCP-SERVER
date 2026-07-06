from collections.abc import Mapping, Sequence

from core import Chunk
from ingestion.transform import MetadataEnricher
from libs.llm import BaseLLM


class FakeLLM(BaseLLM):
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.messages: list[Sequence[Mapping[str, str]]] = []

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        self.messages.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_metadata_enricher_rule_mode_adds_required_fields() -> None:
    chunk = _chunk("# Retrieval Pipeline\nHybrid search combines dense vectors and BM25 keywords.")

    enriched = MetadataEnricher().transform_chunk(chunk)

    assert enriched.text == chunk.text
    assert enriched.id == chunk.id
    assert enriched.start_offset == chunk.start_offset
    assert enriched.end_offset == chunk.end_offset
    assert enriched.source_ref == chunk.source_ref
    assert enriched.metadata["title"] == "Retrieval Pipeline"
    assert enriched.metadata["summary"] == "# Retrieval Pipeline Hybrid search combines dense vectors and BM25 keywords."
    assert enriched.metadata["tags"][:3] == ["pdf", "retrieval", "pipeline"]
    assert enriched.metadata["metadata_enriched"] is True
    assert enriched.metadata["metadata_enrichment_method"] == "rule"
    assert "title" not in chunk.metadata


def test_metadata_enricher_uses_llm_json_when_available() -> None:
    llm = FakeLLM('{"title": "Hybrid Retrieval", "summary": "Combines dense and sparse recall.", "tags": ["rag", "hybrid"]}')
    chunk = _chunk("Dense retrieval plus BM25 keyword search.")

    enriched = MetadataEnricher(llm=llm, prompt_template="Extract metadata.").transform_chunk(chunk)

    assert enriched.metadata["title"] == "Hybrid Retrieval"
    assert enriched.metadata["summary"] == "Combines dense and sparse recall."
    assert enriched.metadata["tags"] == ["rag", "hybrid"]
    assert enriched.metadata["metadata_enrichment_method"] == "llm"
    prompt = llm.messages[0][0]["content"]
    assert "Extract metadata." in prompt
    assert '"text": "Dense retrieval plus BM25 keyword search."' in prompt
    assert '"source_path": "docs/a.pdf"' in prompt


def test_metadata_enricher_fills_missing_llm_fields_from_rules() -> None:
    llm = FakeLLM('{"title": "Only Title", "summary": "", "tags": []}')

    enriched = MetadataEnricher(llm=llm).transform_chunk(_chunk("Chunk text about embeddings and vectors."))

    assert enriched.metadata["title"] == "Only Title"
    assert enriched.metadata["summary"] == "Chunk text about embeddings and vectors."
    assert enriched.metadata["tags"] == ["pdf", "chunk", "text", "about", "embeddings"]
    assert enriched.metadata["metadata_enrichment_method"] == "llm"


def test_metadata_enricher_falls_back_when_llm_returns_invalid_json() -> None:
    llm = FakeLLM("not json")

    enriched = MetadataEnricher(llm=llm).transform_chunk(_chunk("Metadata fallback keeps ingestion moving."))

    assert enriched.metadata["title"] == "Metadata fallback keeps ingestion moving."
    assert enriched.metadata["summary"] == "Metadata fallback keeps ingestion moving."
    assert enriched.metadata["tags"] == ["pdf", "metadata", "fallback", "keeps", "ingestion"]
    assert enriched.metadata["metadata_enrichment_method"] == "rule_fallback"
    assert "metadata_enrichment_fallback_reason" in enriched.metadata


def test_metadata_enricher_falls_back_when_llm_call_fails() -> None:
    llm = FakeLLM(RuntimeError("provider unavailable"))

    enriched = MetadataEnricher(llm=llm).transform_chunk(_chunk("Provider errors should not block indexing."))

    assert enriched.metadata["title"] == "Provider errors should not block indexing."
    assert enriched.metadata["metadata_enrichment_method"] == "rule_fallback"
    assert enriched.metadata["metadata_enrichment_fallback_reason"] == "provider unavailable"


def test_metadata_enricher_preserves_existing_metadata_values_in_rule_mode() -> None:
    chunk = _chunk(
        "Raw chunk text.",
        metadata={"source_path": "docs/a.pdf", "title": "Existing Title", "summary": "Existing summary.", "tags": ["existing"]},
    )

    enriched = MetadataEnricher().transform_chunk(chunk)

    assert enriched.metadata["title"] == "Existing Title"
    assert enriched.metadata["summary"] == "Existing summary."
    assert enriched.metadata["tags"] == ["existing"]


def _chunk(text: str, metadata: dict[str, object] | None = None) -> Chunk:
    return Chunk(
        id="chunk-1",
        text=text,
        metadata=metadata or {"source_path": "docs/a.pdf", "doc_type": "pdf"},
        start_offset=4,
        end_offset=4 + len(text),
        source_ref="doc-1",
    )