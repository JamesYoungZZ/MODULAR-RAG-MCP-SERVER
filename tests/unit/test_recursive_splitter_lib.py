import pytest

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
from libs.splitter import RecursiveSplitter, SplitterFactory


@pytest.fixture(autouse=True)
def reset_splitter_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SplitterFactory, "_strategies", {})


def test_factory_routes_recursive_strategy() -> None:
    splitter = SplitterFactory.create(_settings_with_splitter(strategy="recursive"))

    assert isinstance(splitter, RecursiveSplitter)


def test_recursive_splitter_preserves_markdown_heading_boundaries() -> None:
    splitter = SplitterFactory.create(_settings_with_splitter(chunk_size=70, chunk_overlap=0))
    text = "# Alpha\n\nAlpha paragraph with enough words to form one chunk.\n\n## Beta\n\nBeta paragraph."

    chunks = splitter.split_text(text)

    assert chunks == [
        "# Alpha\n\nAlpha paragraph with enough words to form one chunk.",
        "## Beta\n\nBeta paragraph.",
    ]


def test_recursive_splitter_keeps_small_fenced_code_block_together() -> None:
    splitter = SplitterFactory.create(_settings_with_splitter(chunk_size=140, chunk_overlap=0))
    text = "Intro paragraph.\n\n```python\ndef answer():\n    return 42\n```\n\nClosing paragraph."

    chunks = splitter.split_text(text)

    code_chunks = [chunk for chunk in chunks if "```python" in chunk]

    assert len(code_chunks) == 1
    assert "def answer():" in code_chunks[0]
    assert "return 42" in code_chunks[0]
    assert code_chunks[0].count("```") == 2


def test_recursive_splitter_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="recursive splitter chunk_overlap must be smaller than chunk_size"):
        SplitterFactory.create(_settings_with_splitter(chunk_size=100, chunk_overlap=100))


def test_recursive_splitter_returns_empty_list_for_blank_text() -> None:
    splitter = SplitterFactory.create(_settings_with_splitter())

    assert splitter.split_text("  \n\n  ") == []


def _settings_with_splitter(
    strategy: str = "recursive",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy=strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap),
        vector_store=VectorStoreSettings(backend="chroma", persist_path="./data/db/chroma"),
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