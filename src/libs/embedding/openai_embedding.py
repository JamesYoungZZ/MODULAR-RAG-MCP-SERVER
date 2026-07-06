"""OpenAI-compatible embedding implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.settings import ProviderModelSettings

from libs.embedding.base_embedding import BaseEmbedding


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider request cannot be completed."""


@dataclass(frozen=True)
class EmbeddingEndpoint:
    url: str
    headers: dict[str, str]
    include_model: bool = True


class OpenAIEmbedding(BaseEmbedding):
    """Embedding client for OpenAI-compatible HTTP APIs."""

    default_base_url = "https://api.openai.com/v1"

    def __init__(self, config: ProviderModelSettings, provider: str | None = None) -> None:
        self.config = config
        self.provider = (provider or config.provider).strip().lower()
        self._endpoint = self._build_endpoint()

    def embed(self, texts: list[str], trace: Any | None = None) -> list[list[float]]:
        normalized_texts = self._validate_texts(texts)
        payload: dict[str, Any] = {"input": normalized_texts}
        if self._endpoint.include_model:
            payload["model"] = self._required_model()
        if self.config.dimensions is not None:
            payload["dimensions"] = self.config.dimensions

        request = Request(
            self._endpoint.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._endpoint.headers,
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

    def _build_endpoint(self) -> EmbeddingEndpoint:
        api_key = self._required_api_key()
        base_url = (self.config.base_url or self.default_base_url).rstrip("/")
        return EmbeddingEndpoint(
            url=f"{base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def _validate_texts(self, texts: list[str]) -> list[str]:
        if not isinstance(texts, list) or not texts:
            raise ValueError(f"{self.provider} embedding texts must be a non-empty list")
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{self.provider} embedding texts[{index}] must be a non-empty string")
        return texts

    def _parse_response(self, response_body: str, expected_count: int) -> list[list[float]]:
        try:
            payload = json.loads(response_body)
            data = payload["data"]
            vectors = [item["embedding"] for item in data]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: ResponseParseError") from exc

        if len(vectors) != expected_count:
            raise EmbeddingProviderError(f"{self.provider} embedding request failed: ResponseCountMismatch")
        for vector in vectors:
            if not isinstance(vector, list) or not all(isinstance(value, int | float) for value in vector):
                raise EmbeddingProviderError(f"{self.provider} embedding request failed: ResponseParseError")
        return [[float(value) for value in vector] for vector in vectors]

    def _required_api_key(self) -> str:
        api_key = self.config.api_key
        if not api_key or not api_key.strip():
            raise ValueError(f"{self.provider} embedding requires api_key")
        return api_key

    def _required_model(self) -> str:
        model = self.config.model
        if not model or not model.strip():
            raise ValueError(f"{self.provider} embedding requires model")
        return model


class AzureOpenAIEmbedding(OpenAIEmbedding):
    """Azure OpenAI embedding client using deployment-based endpoints."""

    def _build_endpoint(self) -> EmbeddingEndpoint:
        api_key = self._required_api_key()
        endpoint = self.config.azure_endpoint
        if not endpoint or not endpoint.strip():
            raise ValueError(f"{self.provider} embedding requires azure_endpoint")
        api_version = self.config.api_version
        if not api_version or not api_version.strip():
            raise ValueError(f"{self.provider} embedding requires api_version")
        deployment = self.config.deployment_name or self.config.model
        if not deployment or not deployment.strip():
            raise ValueError(f"{self.provider} embedding requires deployment_name or model")

        base_url = endpoint.rstrip("/")
        return EmbeddingEndpoint(
            url=f"{base_url}/openai/deployments/{deployment}/embeddings?api-version={api_version}",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            include_model=False,
        )


__all__ = ["AzureOpenAIEmbedding", "EmbeddingProviderError", "OpenAIEmbedding"]