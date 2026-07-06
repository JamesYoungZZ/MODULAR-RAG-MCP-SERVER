"""Ollama local LLM implementation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.settings import ProviderModelSettings

from libs.llm.base_llm import BaseLLM
from libs.llm.openai_llm import LLMProviderError


class OllamaLLM(BaseLLM):
    """Chat client for a local Ollama HTTP endpoint."""

    default_base_url = "http://localhost:11434"

    def __init__(self, config: ProviderModelSettings) -> None:
        self.config = config
        self.provider = config.provider.strip().lower()
        self._url = f"{(config.base_url or self.default_base_url).rstrip('/')}/api/chat"

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self._required_model(),
            "messages": self._validate_messages(messages),
            "stream": False,
        }
        options: dict[str, int | float] = {}
        if self.config.temperature is not None:
            options["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            options["num_predict"] = self.config.max_tokens
        if options:
            payload["options"] = options

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
            raise LLMProviderError(f"{self.provider} LLM request failed: HTTPError {exc.code}") from exc
        except URLError as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: URLError {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: TimeoutError") from exc
        except OSError as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: OSError {exc.__class__.__name__}") from exc

        return self._parse_response(response_body)

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
            content = payload["message"]["content"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise LLMProviderError(f"{self.provider} LLM request failed: ResponseParseError") from exc
        if not isinstance(content, str):
            raise LLMProviderError(f"{self.provider} LLM request failed: ResponseParseError")
        return content

    def _required_model(self) -> str:
        model = self.config.model
        if not model or not model.strip():
            raise ValueError(f"{self.provider} LLM requires model")
        return model


__all__ = ["OllamaLLM"]