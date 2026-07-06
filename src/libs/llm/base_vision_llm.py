"""Base Vision LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


ImageInput = str | bytes | Path


class BaseVisionLLM(ABC):
    """Abstract interface for multimodal LLM clients."""

    @abstractmethod
    def chat_with_image(self, text: str, image_path: ImageInput, trace: Any | None = None) -> str:
        """Return a text response for a prompt and an image path or encoded image bytes."""

    def preprocess_image(self, image_path: ImageInput) -> ImageInput:
        """Return a provider-ready image input; providers may override for resize/encoding."""
        return image_path


__all__ = ["BaseVisionLLM", "ImageInput"]