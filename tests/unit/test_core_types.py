import json

import pytest

from core import Chunk, ChunkRecord, Document


def test_document_serializes_with_stable_fields() -> None:
    document = Document(id="doc-1", text="# Title\nBody", metadata={"source_path": "docs/a.pdf", "doc_type": "pdf"})

    payload = document.to_dict()

    assert list(payload) == ["id", "text", "metadata"]
    assert payload == {"id": "doc-1", "text": "# Title\nBody", "metadata": {"source_path": "docs/a.pdf", "doc_type": "pdf"}}
    assert json.loads(json.dumps(payload)) == payload


def test_document_metadata_images_follow_contract() -> None:
    image_id = "abc123_2_1"
    placeholder = f"[IMAGE: {image_id}]"
    text = f"Intro\n{placeholder}\nCaption context"
    document = Document(
        id="doc-1",
        text=text,
        metadata={
            "source_path": "docs/a.pdf",
            "images": [
                {
                    "id": image_id,
                    "path": f"data/images/default/{image_id}.png",
                    "page": 2,
                    "text_offset": text.index(placeholder),
                    "text_length": len(placeholder),
                    "position": {"x": 10, "y": 20, "width": 300, "height": 120},
                }
            ],
        },
    )

    image = document.to_dict()["metadata"]["images"][0]

    assert document.text[image["text_offset"] : image["text_offset"] + image["text_length"]] == placeholder
    assert image["id"] == image_id


def test_chunk_serializes_offsets_and_source_ref() -> None:
    chunk = Chunk(
        id="chunk-1",
        text="Body",
        metadata={"source_path": "docs/a.pdf", "chunk_index": 0},
        start_offset=7,
        end_offset=11,
        source_ref="doc-1",
    )

    assert chunk.to_dict() == {
        "id": "chunk-1",
        "text": "Body",
        "metadata": {"source_path": "docs/a.pdf", "chunk_index": 0},
        "start_offset": 7,
        "end_offset": 11,
        "source_ref": "doc-1",
    }


def test_chunk_record_serializes_optional_vectors() -> None:
    record = ChunkRecord(
        id="chunk-1",
        text="Body",
        metadata={"source_path": "docs/a.pdf"},
        dense_vector=[0.1, 0.2],
        sparse_vector={"body": 1.0},
    )

    assert record.to_dict() == {
        "id": "chunk-1",
        "text": "Body",
        "metadata": {"source_path": "docs/a.pdf"},
        "dense_vector": [0.1, 0.2],
        "sparse_vector": {"body": 1.0},
    }
    assert record.to_vector_record() == {
        "id": "chunk-1",
        "text": "Body",
        "metadata": {"source_path": "docs/a.pdf"},
        "vector": [0.1, 0.2],
    }


def test_metadata_requires_source_path() -> None:
    with pytest.raises(ValueError, match="metadata.source_path must be a non-empty string"):
        Document(id="doc-1", text="Body", metadata={})


def test_image_metadata_validates_required_shape() -> None:
    with pytest.raises(ValueError, match=r"metadata.images\[0\].text_offset must be a non-negative integer"):
        Document(
            id="doc-1",
            text="[IMAGE: bad]",
            metadata={"source_path": "docs/a.pdf", "images": [{"id": "bad", "path": "data/images/default/bad.png", "text_offset": -1, "text_length": 12}]},
        )


def test_chunk_rejects_invalid_offsets() -> None:
    with pytest.raises(ValueError, match="chunk.end_offset must be greater than or equal to start_offset"):
        Chunk(id="chunk-1", text="Body", metadata={"source_path": "docs/a.pdf"}, start_offset=10, end_offset=9)


def test_chunk_record_requires_dense_vector_for_vector_upsert() -> None:
    record = ChunkRecord(id="chunk-1", text="Body", metadata={"source_path": "docs/a.pdf"})

    with pytest.raises(ValueError, match="chunk_record.dense_vector is required for vector upsert"):
        record.to_vector_record()