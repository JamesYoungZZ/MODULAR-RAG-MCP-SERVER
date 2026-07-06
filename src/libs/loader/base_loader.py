"""Base document loader interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from core import Document


class BaseLoader(ABC):
    """Abstract interface for loading source files into Document objects."""

    @abstractmethod
    def load(self, path: str | Path) -> Document:
        """Load a source file and return a normalized Document."""


__all__ = ["BaseLoader"]