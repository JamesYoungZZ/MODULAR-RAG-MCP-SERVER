"""Persistent BM25 inverted index for sparse chunk records."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import ChunkRecord


INDEX_FILENAME = "index.json"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


@dataclass(frozen=True)
class BM25SearchResult:
    id: str
    score: float
    text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "score": self.score, "text": self.text, "metadata": dict(self.metadata)}


class BM25Indexer:
    """Build, persist, load, and query a BM25 inverted index."""

    def __init__(self, index_dir: str | Path = "data/db/bm25", k1: float = 1.5, b: float = 0.75) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than zero")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.index_dir = Path(index_dir)
        self.index_path = self.index_dir / INDEX_FILENAME
        self.k1 = float(k1)
        self.b = float(b)
        self.document_count = 0
        self.average_doc_length = 0.0
        self.index: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}

    def build(self, records: Sequence[ChunkRecord]) -> "BM25Indexer":
        chunk_payloads = [_record_payload(record) for record in records]
        self._rebuild(chunk_payloads)
        return self

    def upsert(self, records: Sequence[ChunkRecord]) -> int:
        current_payloads = list(self.chunks.values())
        incoming_payloads = [_record_payload(record) for record in records]
        incoming_ids = {payload["id"] for payload in incoming_payloads}
        kept_payloads = [payload for payload in current_payloads if payload["id"] not in incoming_ids]
        self._rebuild(kept_payloads + incoming_payloads)
        return len(incoming_payloads)

    def query(self, query: str | Mapping[str, float], top_k: int = 10) -> list[BM25SearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be greater than zero")
        query_terms = _query_terms(query)
        if not query_terms or self.document_count == 0:
            return []

        scores: dict[str, float] = {}
        for term, query_weight in query_terms.items():
            entry = self.index.get(term)
            if entry is None:
                continue
            idf = abs(float(entry["idf"]))
            for posting in entry["postings"]:
                chunk_id = str(posting["chunk_id"])
                tf = float(posting["tf"])
                doc_length = float(posting["doc_length"])
                scores[chunk_id] = scores.get(chunk_id, 0.0) + query_weight * idf * self._term_score(tf, doc_length)

        ranked_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:top_k]
        return [
            BM25SearchResult(
                id=chunk_id,
                score=scores[chunk_id],
                text=str(self.chunks[chunk_id]["text"]),
                metadata=dict(self.chunks[chunk_id]["metadata"]),
            )
            for chunk_id in ranked_ids
        ]

    def save(self) -> Path:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "k1": self.k1,
            "b": self.b,
            "document_count": self.document_count,
            "average_doc_length": self.average_doc_length,
            "chunks": self.chunks,
            "index": self.index,
        }
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return self.index_path

    def load(self) -> "BM25Indexer":
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"BM25 index not found: {self.index_path}") from exc

        self.k1 = float(payload.get("k1", self.k1))
        self.b = float(payload.get("b", self.b))
        self.document_count = int(payload.get("document_count", 0))
        self.average_doc_length = float(payload.get("average_doc_length", 0.0))
        self.chunks = {str(chunk_id): dict(chunk) for chunk_id, chunk in payload.get("chunks", {}).items()}
        self.index = {str(term): dict(entry) for term, entry in payload.get("index", {}).items()}
        return self

    def _rebuild(self, chunk_payloads: Sequence[dict[str, Any]]) -> None:
        self.chunks = {payload["id"]: dict(payload) for payload in chunk_payloads}
        self.document_count = len(self.chunks)
        total_length = sum(float(payload["doc_length"]) for payload in self.chunks.values())
        self.average_doc_length = total_length / self.document_count if self.document_count else 0.0

        postings_by_term: dict[str, list[dict[str, Any]]] = {}
        for payload in self.chunks.values():
            for term, tf in payload["sparse_vector"].items():
                postings_by_term.setdefault(term, []).append(
                    {"chunk_id": payload["id"], "tf": float(tf), "doc_length": float(payload["doc_length"])}
                )

        self.index = {}
        for term, postings in sorted(postings_by_term.items()):
            document_frequency = len(postings)
            self.index[term] = {
                "idf": _idf(self.document_count, document_frequency),
                "postings": sorted(postings, key=lambda posting: str(posting["chunk_id"])),
            }

    def _term_score(self, tf: float, doc_length: float) -> float:
        if self.average_doc_length <= 0:
            return 0.0
        denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.average_doc_length)
        return (tf * (self.k1 + 1)) / denominator if denominator else 0.0


def _record_payload(record: ChunkRecord) -> dict[str, Any]:
    if record.sparse_vector is None:
        raise ValueError("chunk_record.sparse_vector is required for BM25 indexing")
    doc_length = record.metadata.get("sparse_doc_length")
    if not isinstance(doc_length, int | float):
        doc_length = sum(record.sparse_vector.values())
    return {
        "id": record.id,
        "text": record.text,
        "metadata": dict(record.metadata),
        "sparse_vector": dict(record.sparse_vector),
        "doc_length": float(doc_length),
    }


def _query_terms(query: str | Mapping[str, float]) -> dict[str, float]:
    if isinstance(query, str):
        terms: dict[str, float] = {}
        for match in TOKEN_PATTERN.finditer(query.lower()):
            term = match.group(0).strip("_-")
            if term:
                terms[term] = terms.get(term, 0.0) + 1.0
        return terms
    if isinstance(query, Mapping):
        return {str(term): float(weight) for term, weight in query.items() if float(weight) > 0}
    raise ValueError("query must be a string or sparse vector mapping")


def _idf(document_count: int, document_frequency: int) -> float:
    if document_count < 1 or document_frequency < 1:
        return 0.0
    return math.log((document_count - document_frequency + 0.5) / (document_frequency + 0.5))


__all__ = ["BM25Indexer", "BM25SearchResult", "INDEX_FILENAME"]