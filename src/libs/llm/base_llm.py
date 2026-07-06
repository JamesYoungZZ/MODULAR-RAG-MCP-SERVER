"""Base LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence


class BaseLLM(ABC):
    """Abstract interface for chat-oriented LLM clients."""

    @abstractmethod
    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        """Return a text response for chat messages."""


__all__ = ["BaseLLM"]