"""OpenAI-compatible chat LLM implementations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.settings import ProviderModelSettings

from libs.llm.base_llm import BaseLLM


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider request cannot be completed."""


@dataclass(frozen=True)
class ProviderEndpoint:
    url: str
    headers: dict[str, str]
    include_model: bool = True


class OpenAICompatibleLLM(BaseLLM):
    """Chat client for OpenAI-compatible HTTP APIs."""

    default_base_url = "https://api.openai.com/v1"


    def __init__(self, config: ProviderModelSettings, provider: str | None = None) -> None:
        self.config = config
        self.provider = (provider or config.provider).strip().lower()
        self._endpoint = self._build_endpoint()

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        normalized_messages = self._validate_messages(messages)
        payload: dict[str, Any] = {"messages": normalized_messages}
        if self._endpoint.include_model:
            payload["model"] = self._required_model()
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens

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
            raise LLMProviderError(f"{self.provider} LLM request failed: HTTPError {exc.code}") from exc
        except URLError as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: URLError {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: TimeoutError") from exc
        except OSError as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: OSError {exc.__class__.__name__}") from exc

        return self._parse_response(response_body)

    def _build_endpoint(self) -> ProviderEndpoint:
        api_key = self._required_api_key()
        base_url = (self.config.base_url or self.default_base_url).rstrip("/")
        return ProviderEndpoint(
            url=f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def _validate_messages(self, messages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        if not isinstance(messages, Sequence) or isinstance(messages, str) or not messages:
            raise ValueError(f"{self.provider} LLM messages must be a non-empty sequence")

        normalized_messages: list[dict[str, str]] = []
        for index, message in enumerate(messages):
            if not isinstance(message, Mapping):
                raise ValueError(f"{self.provider} LLM message[{index}] must be a mapping")
            role = message.get("role")
            content = message.get("content")
            if not isinstance(role, str) or not role.strip():
                raise ValueError(f"{self.provider} LLM message[{index}].role must be a non-empty string")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"{self.provider} LLM message[{index}].content must be a non-empty string")
            normalized_messages.append({"role": role, "content": content})
        return normalized_messages

    def _parse_response(self, response_body: str) -> str:
        try:
            payload = json.loads(response_body)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: ResponseParseError") from exc
        if not isinstance(content, str):
            raise LLMProviderError(f"{self.provider} LLM request failed: ResponseParseError")
        return content

    def _required_api_key(self) -> str:
        api_key = self.config.api_key
        if not api_key or not api_key.strip():
            raise ValueError(f"{self.provider} LLM requires api_key")
        return api_key

    def _required_model(self) -> str:
        model = self.config.model
        if not model or not model.strip():
            raise ValueError(f"{self.provider} LLM requires model")
        return model


class DeepSeekLLM(OpenAICompatibleLLM):
    """DeepSeek chat client using the OpenAI-compatible API shape."""

    default_base_url = "https://api.deepseek.com/v1"


class AzureOpenAILLM(OpenAICompatibleLLM):
    """Azure OpenAI chat client using deployment-based chat completions."""

    def _build_endpoint(self) -> ProviderEndpoint:
        api_key = self._required_api_key()
        endpoint = self.config.azure_endpoint
        if not endpoint or not endpoint.strip():
            raise ValueError(f"{self.provider} LLM requires azure_endpoint")
        api_version = self.config.api_version
        if not api_version or not api_version.strip():
            raise ValueError(f"{self.provider} LLM requires api_version")
        deployment = self.config.deployment_name or self.config.model
        if not deployment or not deployment.strip():
            raise ValueError(f"{self.provider} LLM requires deployment_name or model")

        base_url = endpoint.rstrip("/")
        return ProviderEndpoint(
            url=f"{base_url}/openai/deployments/{deployment}/chat/completions?api-version={api_version}",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            include_model=False,
        )


__all__ = ["AzureOpenAILLM", "DeepSeekLLM", "LLMProviderError", "OpenAICompatibleLLM"]