"""Query preprocessing for retrieval routes."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
FILTER_PATTERN = re.compile(r'(?P<field>[A-Za-z_][A-Za-z0-9_.-]*):(?P<value>"[^"]+"|\'[^\']+\'|[^\s]+)')
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
DEFAULT_FILTER_FIELDS = {
    "access_level",
    "collection",
    "doc_type",
    "language",
    "source",
    "source_path",
    "tags",
    "title",
}


@dataclass(frozen=True)
class ProcessedQuery:
    original_query: str
    semantic_query: str
    keywords: list[str]
    sparse_query: dict[str, float]
    filters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "semantic_query": self.semantic_query,
            "keywords": list(self.keywords),
            "sparse_query": dict(self.sparse_query),
            "filters": dict(self.filters),
        }


class QueryProcessor:
    """Normalize user queries into dense text, sparse terms, and metadata filters."""

    def __init__(
        self,
        stopwords: set[str] | None = None,
        filter_fields: Sequence[str] | None = None,
        aliases: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.stopwords = STOPWORDS if stopwords is None else {word.lower() for word in stopwords}
        self.filter_fields = DEFAULT_FILTER_FIELDS if filter_fields is None else {field.strip() for field in filter_fields if field.strip()}
        self.aliases = _normalize_aliases(aliases or {})

    def process(self, query: str, filters: Mapping[str, Any] | None = None) -> ProcessedQuery:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        inline_filters, semantic_query = self._extract_inline_filters(query)
        merged_filters = _merge_filters(inline_filters, filters)
        keywords = self._extract_keywords(semantic_query)
        sparse_query = self._sparse_query(keywords)
        return ProcessedQuery(
            original_query=query,
            semantic_query=semantic_query,
            keywords=keywords,
            sparse_query=sparse_query,
            filters=merged_filters,
        )

    def _extract_inline_filters(self, query: str) -> tuple[dict[str, Any], str]:
        filters: dict[str, Any] = {}
        spans_to_remove: list[tuple[int, int]] = []
        for match in FILTER_PATTERN.finditer(query):
            field = match.group("field")
            if field not in self.filter_fields:
                continue
            filters[field] = _parse_filter_value(match.group("value"))
            spans_to_remove.append(match.span())

        semantic_parts: list[str] = []
        cursor = 0
        for start, end in spans_to_remove:
            semantic_parts.append(query[cursor:start])
            cursor = end
        semantic_parts.append(query[cursor:])
        semantic_query = _normalize_whitespace("".join(semantic_parts))
        return filters, semantic_query

    def _extract_keywords(self, query: str) -> list[str]:
        keywords: list[str] = []
        seen: set[str] = set()
        for match in TOKEN_PATTERN.finditer(query.lower()):
            token = match.group(0).strip("_-")
            if token and token not in self.stopwords and token not in seen:
                seen.add(token)
                keywords.append(token)
        return keywords

    def _sparse_query(self, keywords: Sequence[str]) -> dict[str, float]:
        sparse_query: dict[str, float] = {}
        for keyword in keywords:
            sparse_query[keyword] = sparse_query.get(keyword, 0.0) + 1.0
            for alias in self.aliases.get(keyword, []):
                sparse_query[alias] = sparse_query.get(alias, 0.0) + 0.5
        return sparse_query


def _merge_filters(inline_filters: Mapping[str, Any], filters: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(inline_filters)
    if filters is None:
        return merged
    if not isinstance(filters, Mapping):
        raise ValueError("filters must be a mapping")
    for key, value in filters.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("filter keys must be non-empty strings")
        if value is not None:
            merged[key] = value
    return merged


def _parse_filter_value(value: str) -> str | list[str]:
    stripped = value.strip().strip('"\'')
    if "," not in stripped:
        return stripped
    return [part.strip() for part in stripped.split(",") if part.strip()]


def _normalize_aliases(aliases: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for keyword, values in aliases.items():
        key = str(keyword).strip().lower()
        if not key:
            continue
        normalized[key] = [str(value).strip().lower() for value in values if str(value).strip()]
    return normalized


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


__all__ = ["ProcessedQuery", "QueryProcessor"]