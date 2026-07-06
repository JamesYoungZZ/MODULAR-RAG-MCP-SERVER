"""Recursive text splitter implementation."""

from __future__ import annotations

from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.settings import SplitterSettings

from libs.splitter.base_splitter import BaseSplitter


class RecursiveSplitter(BaseSplitter):
    """Markdown-aware wrapper around LangChain's recursive character splitter."""

    markdown_separators = [
        "\n```\n",
        "\n# ",
        "\n## ",
        "\n### ",
        "\n#### ",
        "\n##### ",
        "\n###### ",
        "\n\n",
        "\n",
        " ",
        "",
    ]

    def __init__(self, config: SplitterSettings) -> None:
        if config.chunk_size <= 0:
            raise ValueError("recursive splitter chunk_size must be greater than 0")
        if config.chunk_overlap < 0:
            raise ValueError("recursive splitter chunk_overlap must be greater than or equal to 0")
        if config.chunk_overlap >= config.chunk_size:
            raise ValueError("recursive splitter chunk_overlap must be smaller than chunk_size")

        self.config = config
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=self.markdown_separators,
            keep_separator="start",
        )

    def split_text(self, text: str, trace: Any | None = None) -> list[str]:
        if not isinstance(text, str):
            raise ValueError("recursive splitter text must be a string")
        if not text.strip():
            return []
        return [chunk.strip() for chunk in self._splitter.split_text(text) if chunk.strip()]


__all__ = ["RecursiveSplitter"]