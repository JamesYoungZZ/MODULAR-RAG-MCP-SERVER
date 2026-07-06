"""Chroma vector store implementation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import chromadb

from core.settings import VectorStoreSettings

from libs.vector_store.base_vector_store import BaseVectorStore, VectorQueryResult, VectorRecord


class ChromaStore(BaseVectorStore):
    """Persistent Chroma-backed vector store."""

    default_collection = "default"

    def __init__(self, config: VectorStoreSettings) -> None:
        self.config = config
        persist_path = Path(config.persist_path)
        persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_path))
        self._collection = self._client.get_or_create_collection(name=self.default_collection)

    def upsert(self, records: Sequence[VectorRecord], trace: Any | None = None) -> int:
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise ValueError("records must be a sequence of vector records")
        if not records:
            return 0

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for record in records:
            record_id, vector, text, metadata = self._validate_record(record)
            ids.append(record_id)
            embeddings.append(vector)
            documents.append(text)
            metadatas.append(metadata)

        self._collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        return len(ids)

    def query(
        self,
        vector: Sequence[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
        trace: Any | None = None,
    ) -> list[VectorQueryResult]:
        query_vector = self._validate_query_vector(vector)
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be greater than zero")
        where = self._validate_filters(filters)

        raw_results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = raw_results.get("ids", [[]])[0]
        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]

        results: list[VectorQueryResult] = []
        for index, record_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 0.0
            results.append(
                {
                    "id": record_id,
                    "score": 1.0 / (1.0 + distance),
                    "metadata": metadatas[index] if index < len(metadatas) and metadatas[index] else {},
                    "text": documents[index] if index < len(documents) and documents[index] else "",
                }
            )
        return results

    def _validate_record(self, record: VectorRecord) -> tuple[str, list[float], str, dict[str, Any]]:
        if not isinstance(record, Mapping):
            raise ValueError("record must be a mapping")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record.id must be a non-empty string")
        vector = record.get("vector")
        if not isinstance(vector, list) or not vector or not all(isinstance(value, float) for value in vector):
            raise ValueError("record.vector must be a non-empty list of floats")
        text = record.get("text")
        if not isinstance(text, str):
            raise ValueError("record.text must be a string")
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("record.metadata must be a mapping")
        return record_id, vector, text, metadata

    def _validate_query_vector(self, vector: Sequence[float]) -> list[float]:
        if not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)) or not vector:
            raise ValueError("query vector must be a non-empty sequence of floats")
        if not all(isinstance(value, float) for value in vector):
            raise ValueError("query vector must be a non-empty sequence of floats")
        return list(vector)

    def _validate_filters(self, filters: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if filters is None:
            return None
        if not isinstance(filters, Mapping):
            raise ValueError("filters must be a mapping")
        return dict(filters)


__all__ = ["ChromaStore"]