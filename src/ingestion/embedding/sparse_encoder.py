"""Sparse term encoder for BM25-style indexing."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import Any

from core import Chunk, ChunkRecord


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


class SparseEncoder:
    """Encode Chunk text into sparse term-frequency vectors."""

    def __init__(self, stopwords: set[str] | None = None) -> None:
        self.stopwords = STOPWORDS if stopwords is None else {word.lower() for word in stopwords}

    def encode_chunks(self, chunks: Sequence[Chunk], trace: Any | None = None) -> list[ChunkRecord]:
        return [self.encode_chunk(chunk, trace=trace) for chunk in chunks]

    def encode_chunk(self, chunk: Chunk, trace: Any | None = None) -> ChunkRecord:
        tokens = _tokenize(chunk.text, self.stopwords)
        term_counts = Counter(tokens)
        metadata = dict(chunk.metadata)
        metadata["sparse_doc_length"] = len(tokens)
        metadata["sparse_unique_terms"] = len(term_counts)
        return ChunkRecord(
            id=chunk.id,
            text=chunk.text,
            metadata=metadata,
            sparse_vector={term: float(count) for term, count in sorted(term_counts.items())},
        )


def _tokenize(text: str, stopwords: set[str]) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_PATTERN.finditer(text.lower()):
        token = match.group(0).strip("_-")
        if token and token not in stopwords:
            tokens.append(token)
    return tokens


__all__ = ["SparseEncoder"]