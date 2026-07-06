"""Ollama local embedding implementation."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.settings import ProviderModelSettings

from libs.embedding.base_embedding import BaseEmbedding
from libs.embedding.openai_embedding import EmbeddingProviderError


class OllamaEmbedding(BaseEmbedding):
    """Embedding client for a local Ollama HTTP endpoint."""

    default_base_url = "http://localhost:11434"
    max_input_chars = 32768

    def __init__(self, config: ProviderModelSettings) -> None:
        self.config = config
        self.provider = config.provider.strip().lower()
        self._url = f"{(config.base_url or self.default_base_url).rstrip('/')}/api/embed"

    def embed(self, texts: list[str], trace: Any | None = None) -> list[list[float]]:
        normalized_texts = self._validate_texts(texts)
        payload = {
            "model": self._required_model(),
            "input": normalized_texts,
        }
        request = Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: HTTPError {exc.code}") from exc
        except URLError as exc:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: URLError {exc.reason}") from exc
        except TimeoutError as exc:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: TimeoutError") from exc
        except OSError as exc:
            raise EmbeddingProviderError(
                f"{self.provider} embedding request failed: OSError {exc.__class__.__name__}"
            ) from exc

        return self._parse_response(response_body, expected_count=len(normalized_texts))

    def _validate_texts(self, texts: list[str]) -> list[str]:
        if not isinstance(texts, list) or not texts:
            raise ValueError(f"{self.provider} embedding texts must be a non-empty list")
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{self.provider} embedding texts[{index}] must be a non-empty string")
            if len(text) > self.max_input_chars:
                raise ValueError(
                    f"{self.provider} embedding texts[{index}] exceeds max_input_chars={self.max_input_chars}"
                )
        return texts

    def _parse_response(self, response_body: str, expected_count: int) -> list[list[float]]:
        try:
            payload = json.loads(response_body)
            vectors = payload["embeddings"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: ResponseParseError") from exc

        if len(vectors) != expected_count:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: ResponseCountMismatch")
        for vector in vectors:
            if not isinstance(vector, list) or not all(isinstance(value, int | float) for value in vector):
                raise EmbeddingProviderError(f"{self.provider} embedding request failed: ResponseParseError")
        return [[float(value) for value in vector] for vector in vectors]

    def _required_model(self) -> str:
        model = self.config.model
        if not model or not model.strip():
            raise ValueError(f"{self.provider} embedding requires model")
        return model


__all__ = ["OllamaEmbedding"]