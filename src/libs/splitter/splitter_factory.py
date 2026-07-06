"""Factory for splitter strategies."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import Settings, SplitterSettings

from libs.splitter.base_splitter import BaseSplitter


SplitterBuilder = Callable[[SplitterSettings], BaseSplitter]


class SplitterFactory:
    """Create splitters from settings using a strategy registry."""

    _strategies: dict[str, SplitterBuilder] = {}

    @classmethod
    def register_strategy(cls, strategy: str, builder: SplitterBuilder) -> None:
        strategy_key = _normalize_strategy(strategy)
        if not strategy_key:
            raise ValueError("Splitter strategy name must not be empty")
        cls._strategies[strategy_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> BaseSplitter:
        strategy_key = _normalize_strategy(settings.splitter.strategy)
        if strategy_key not in cls._strategies:
            available = ", ".join(sorted(cls._strategies)) or "none"
            raise ValueError(
                f"Unsupported splitter strategy: {settings.splitter.strategy}. Available strategies: {available}"
            )
        return cls._strategies[strategy_key](settings.splitter)


def _normalize_strategy(strategy: str) -> str:
    return strategy.strip().lower()


__all__ = ["SplitterBuilder", "SplitterFactory"]