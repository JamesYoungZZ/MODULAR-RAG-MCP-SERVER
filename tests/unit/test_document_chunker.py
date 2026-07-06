from core import Chunk, Document
from core.settings import (
    EvaluationSettings,
    ObservabilitySettings,
    ProviderModelSettings,
    RerankSettings,
    RetrievalSettings,
    Settings,
    SplitterSettings,
    VectorStoreSettings,
)
from ingestion.chunking import DocumentChunker
from libs.splitter import BaseSplitter


class FakeSplitter(BaseSplitter):
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def split_text(self, text: str, trace: object | None = None) -> list[str]:
        return self.chunks


def test_document_chunker_converts_split_text_to_chunks() -> None:
    document = Document(id="doc-1", text="Alpha\nBeta", metadata={"source_path": "docs/a.pdf", "doc_type": "pdf"})
    chunker = DocumentChunker(_settings(), splitter=FakeSplitter(["Alpha", "Beta"]))

    chunks = chunker.split_document(document)

    assert [type(chunk) for chunk in chunks] == [Chunk, Chunk]
    assert [chunk.text for chunk in chunks] == ["Alpha", "Beta"]
    assert [chunk.source_ref for chunk in chunks] == ["doc-1", "doc-1"]
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1]
    assert chunks[0].metadata["source_path"] == "docs/a.pdf"
    assert chunks[0].metadata["doc_type"] == "pdf"


def test_document_chunker_generates_unique_and_deterministic_ids() -> None:
    document = Document(id="doc-1", text="Alpha\nBeta", metadata={"source_path": "docs/a.pdf"})
    chunker = DocumentChunker(_settings(), splitter=FakeSplitter(["Alpha", "Beta"]))

    first_ids = [chunk.id for chunk in chunker.split_document(document)]
    second_ids = [chunk.id for chunk in chunker.split_document(document)]

    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids))
    assert first_ids[0].startswith("doc-1_0000_")
    assert first_ids[1].startswith("doc-1_0001_")


def test_document_chunker_records_offsets() -> None:
    document = Document(id="doc-1", text="Alpha\nBeta\nGamma", metadata={"source_path": "docs/a.pdf"})
    chunker = DocumentChunker(_settings(), splitter=FakeSplitter(["Beta", "Gamma"]))

    chunks = chunker.split_document(document)

    assert [(chunk.start_offset, chunk.end_offset) for chunk in chunks] == [(6, 10), (11, 16)]


def test_document_chunker_distributes_only_referenced_images() -> None:
    image_one = _image("img-1")
    image_two = _image("img-2")
    document = Document(
        id="doc-1",
        text="Intro [IMAGE: img-1]\nOther [IMAGE: img-2]",
        metadata={"source_path": "docs/a.pdf", "images": [image_one, image_two]},
    )
    chunker = DocumentChunker(_settings(), splitter=FakeSplitter(["Intro [IMAGE: img-1]", "Other text"]))

    first_chunk, second_chunk = chunker.split_document(document)

    assert first_chunk.metadata["image_refs"] == ["img-1"]
    assert first_chunk.metadata["images"] == [image_one]
    assert "images" not in second_chunk.metadata
    assert "image_refs" not in second_chunk.metadata


def test_document_chunker_preserves_multiple_image_reference_order_without_duplicates() -> None:
    image_one = _image("img-1")
    image_two = _image("img-2")
    document = Document(
        id="doc-1",
        text="[IMAGE: img-2] [IMAGE: img-1] [IMAGE: img-2]",
        metadata={"source_path": "docs/a.pdf", "images": [image_one, image_two]},
    )
    chunker = DocumentChunker(_settings(), splitter=FakeSplitter([document.text]))

    chunk = chunker.split_document(document)[0]

    assert chunk.metadata["image_refs"] == ["img-2", "img-1"]
    assert chunk.metadata["images"] == [image_two, image_one]


def test_document_chunker_uses_splitter_factory_when_splitter_not_injected(monkeypatch) -> None:
    document = Document(id="doc-1", text="Alpha\nBeta", metadata={"source_path": "docs/a.pdf"})

    from libs.splitter import SplitterFactory

    monkeypatch.setattr(SplitterFactory, "create", lambda settings: FakeSplitter(["Alpha", "Beta"]))

    chunks = DocumentChunker(_settings()).split_document(document)

    assert [chunk.text for chunk in chunks] == ["Alpha", "Beta"]


def _image(image_id: str) -> dict[str, object]:
    return {
        "id": image_id,
        "path": f"data/images/default/{image_id}.png",
        "page": 1,
        "text_offset": 0,
        "text_length": len(f"[IMAGE: {image_id}]"),
        "position": {},
    }


def _settings() -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy="recursive", chunk_size=1000, chunk_overlap=200),
        vector_store=VectorStoreSettings(backend="fake", persist_path="./tmp/vector"),
        retrieval=RetrievalSettings(
            sparse_backend="bm25",
            fusion_algorithm="rrf",
            top_k_dense=20,
            top_k_sparse=20,
            top_k_final=10,
        ),
        rerank=RerankSettings(backend="none", model=None, top_m=30),
        evaluation=EvaluationSettings(backends=[], golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )