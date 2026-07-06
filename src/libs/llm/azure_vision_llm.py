"""Azure OpenAI Vision LLM implementation."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from core.settings import ProviderModelSettings

from libs.llm.base_vision_llm import BaseVisionLLM, ImageInput
from libs.llm.openai_llm import LLMProviderError


class AzureVisionLLM(BaseVisionLLM):
    """Azure OpenAI multimodal chat client."""

    default_max_image_size = 2048

    def __init__(self, config: ProviderModelSettings) -> None:
        self.config = config
        self.provider = config.provider.strip().lower()
        self._url = self._build_url()

    def chat_with_image(self, text: str, image_path: ImageInput, trace: Any | None = None) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("azure vision LLM text must be a non-empty string")

        payload: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": self.preprocess_image(image_path)}},
                    ],
                }
            ]
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens

        request = Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"api-key": self._required_api_key(), "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise LLMProviderError(f"azure vision LLM request failed: AzureHTTPError {exc.code}") from exc
        except URLError as exc:
            raise LLMProviderError(f"azure vision LLM request failed: URLError {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMProviderError("azure vision LLM request failed: TimeoutError") from exc
        except OSError as exc:
            raise LLMProviderError(f"azure vision LLM request failed: OSError {exc.__class__.__name__}") from exc

        return self._parse_response(response_body)

    def preprocess_image(self, image_path: ImageInput) -> str:
        image_bytes, mime_type = self._image_bytes_and_mime(image_path)
        resized_bytes, resized_mime_type = self._resize_if_needed(image_bytes, mime_type)
        encoded_image = base64.b64encode(resized_bytes).decode("ascii")
        return f"data:{resized_mime_type};base64,{encoded_image}"

    def _build_url(self) -> str:
        endpoint = self.config.azure_endpoint
        if not endpoint or not endpoint.strip():
            raise ValueError("azure vision LLM requires azure_endpoint")
        api_version = self.config.api_version
        if not api_version or not api_version.strip():
            raise ValueError("azure vision LLM requires api_version")
        deployment = self.config.deployment_name or self.config.model
        if not deployment or not deployment.strip():
            raise ValueError("azure vision LLM requires deployment_name or model")
        return f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    def _image_bytes_and_mime(self, image_path: ImageInput) -> tuple[bytes, str]:
        if isinstance(image_path, Path) or (isinstance(image_path, str) and Path(image_path).exists()):
            path = Path(image_path)
            return path.read_bytes(), self._mime_type_for_suffix(path.suffix)

        if isinstance(image_path, bytes):
            encoded_image = image_path.decode("ascii")
            return base64.b64decode(encoded_image, validate=True), "image/png"

        if isinstance(image_path, str):
            if image_path.startswith("data:image/"):
                header, encoded_image = image_path.split(",", 1)
                mime_type = header.removeprefix("data:").split(";", 1)[0]
                return base64.b64decode(encoded_image, validate=True), mime_type
            return base64.b64decode(image_path, validate=True), "image/png"

        raise ValueError("azure vision LLM image_path must be a path, base64 string, data URL, or base64 bytes")

    def _resize_if_needed(self, image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
        max_image_size = self.config.max_image_size or self.default_max_image_size
        with Image.open(BytesIO(image_bytes)) as image:
            if image.width <= max_image_size and image.height <= max_image_size:
                return image_bytes, mime_type

            image.thumbnail((max_image_size, max_image_size))
            output = BytesIO()
            image_format = image.format or self._format_for_mime_type(mime_type)
            if image_format.upper() == "JPEG" and image.mode in {"RGBA", "P"}:
                image = image.convert("RGB")
            image.save(output, format=image_format)
            return output.getvalue(), self._mime_type_for_format(image_format)

    def _parse_response(self, response_body: str) -> str:
        try:
            payload = json.loads(response_body)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMProviderError("azure vision LLM request failed: ResponseParseError") from exc
        if not isinstance(content, str):
            raise LLMProviderError("azure vision LLM request failed: ResponseParseError")
        return content

    def _required_api_key(self) -> str:
        api_key = self.config.api_key
        if not api_key or not api_key.strip():
            raise ValueError("azure vision LLM requires api_key")
        return api_key

    def _mime_type_for_suffix(self, suffix: str) -> str:
        normalized_suffix = suffix.lower()
        if normalized_suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if normalized_suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _format_for_mime_type(self, mime_type: str) -> str:
        if mime_type == "image/jpeg":
            return "JPEG"
        if mime_type == "image/webp":
            return "WEBP"
        return "PNG"

    def _mime_type_for_format(self, image_format: str) -> str:
        if image_format.upper() == "JPEG":
            return "image/jpeg"
        if image_format.upper() == "WEBP":
            return "image/webp"
        return "image/png"


__all__ = ["AzureVisionLLM"]