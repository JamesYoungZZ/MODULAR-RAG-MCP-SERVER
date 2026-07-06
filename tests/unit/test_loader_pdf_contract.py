from pathlib import Path

import pytest

from core import Document
from libs.loader import BaseLoader, PdfLoader


def test_pdf_loader_loads_pdf_as_document(tmp_path) -> None:
    pdf_path = _write_minimal_pdf(tmp_path / "sample.pdf", "Hello PDF")
    loader = PdfLoader(image_output_root=tmp_path / "images")

    document = loader.load(pdf_path)

    assert isinstance(document, Document)
    assert document.text == "Hello PDF"
    assert document.metadata["source_path"] == str(pdf_path)
    assert document.metadata["doc_type"] == "pdf"
    assert document.metadata["images"] == []
    assert document.id == document.metadata["file_hash"]


def test_pdf_loader_can_use_injected_converter(tmp_path) -> None:
    pdf_path = _write_minimal_pdf(tmp_path / "sample.pdf", "Raw text")
    loader = PdfLoader(converter=lambda path: "# Converted\nBody", image_output_root=tmp_path / "images")

    document = loader.load(pdf_path)

    assert document.text == "# Converted\nBody"


def test_pdf_loader_records_extracted_images_and_placeholders(tmp_path) -> None:
    pdf_path = _write_minimal_pdf(tmp_path / "with-image.pdf", "Body")
    source_image = tmp_path / "image.png"
    source_image.write_bytes(b"png-bytes")

    def extract_images(path: Path, doc_hash: str, output_dir: Path) -> list[dict[str, object]]:
        return [{"id": f"{doc_hash}_2_1", "path": str(source_image), "page": 2, "position": {"x": 1, "y": 2}}]

    loader = PdfLoader(converter=lambda path: "Body", image_extractor=extract_images, image_output_root=tmp_path / "images")

    document = loader.load(pdf_path)

    image = document.metadata["images"][0]
    placeholder = f"[IMAGE: {image['id']}]"

    assert placeholder in document.text
    assert document.text[image["text_offset"] : image["text_offset"] + image["text_length"]] == placeholder
    assert image["page"] == 2
    assert image["path"] == str(tmp_path / "images" / document.id / f"{image['id']}.png")
    assert Path(image["path"]).read_bytes() == b"png-bytes"


def test_pdf_loader_image_extraction_failure_does_not_block_text(tmp_path) -> None:
    pdf_path = _write_minimal_pdf(tmp_path / "sample.pdf", "Hello PDF")

    def extract_images(path: Path, doc_hash: str, output_dir: Path) -> list[dict[str, object]]:
        raise RuntimeError("image backend unavailable")

    loader = PdfLoader(image_extractor=extract_images, image_output_root=tmp_path / "images")

    document = loader.load(pdf_path)

    assert document.text == "Hello PDF"
    assert document.metadata["images"] == []


def test_pdf_loader_rejects_non_pdf_files(tmp_path) -> None:
    source_path = tmp_path / "notes.txt"
    source_path.write_text("not a pdf", encoding="utf-8")
    loader = PdfLoader(image_output_root=tmp_path / "images")

    with pytest.raises(ValueError, match="PdfLoader only supports .pdf files"):
        loader.load(source_path)


def test_pdf_loader_implements_base_loader_contract(tmp_path) -> None:
    pdf_path = _write_minimal_pdf(tmp_path / "sample.pdf", "Hello PDF")
    loader: BaseLoader = PdfLoader(image_output_root=tmp_path / "images")

    assert isinstance(loader.load(pdf_path), Document)


def _write_minimal_pdf(path: Path, text: str) -> Path:
    escaped_text = text.replace("(", r"\(").replace(")", r"\)")
    path.write_text(
        "\n".join(
            [
                "%PDF-1.4",
                "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
                "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
                "3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj",
                f"4 0 obj << /Length {len(escaped_text) + 20} >> stream",
                "BT",
                f"({escaped_text}) Tj",
                "ET",
                "endstream endobj",
                "%%EOF",
            ]
        ),
        encoding="latin-1",
    )
    return path