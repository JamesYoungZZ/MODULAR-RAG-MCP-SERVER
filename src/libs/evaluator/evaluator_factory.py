"""Factory for evaluator backends."""

from __future__ import annotations

from collections.abc import Callable

from core.settings import EvaluationSettings, Settings

from libs.evaluator.base_evaluator import BaseEvaluator
from libs.evaluator.custom_evaluator import CustomEvaluator


EvaluatorBuilder = Callable[[EvaluationSettings], BaseEvaluator]


class EvaluatorFactory:
    """Create evaluators from settings using a backend registry."""

    _backends: dict[str, EvaluatorBuilder] = {"custom": lambda config: CustomEvaluator()}

    @classmethod
    def register_backend(cls, backend: str, builder: EvaluatorBuilder) -> None:
        backend_key = _normalize_backend(backend)
        if not backend_key:
            raise ValueError("Evaluator backend name must not be empty")
        cls._backends[backend_key] = builder

    @classmethod
    def create(cls, settings: Settings) -> list[BaseEvaluator]:
        evaluators: list[BaseEvaluator] = []
        for backend in settings.evaluation.backends:
            backend_key = _normalize_backend(backend)
            if backend_key not in cls._backends:
                available = ", ".join(sorted(cls._backends)) or "none"
                raise ValueError(f"Unsupported evaluator backend: {backend}. Available backends: {available}")
            evaluators.append(cls._backends[backend_key](settings.evaluation))
        return evaluators


def _normalize_backend(backend: str) -> str:
    return backend.strip().lower()


__all__ = ["EvaluatorBuilder", "EvaluatorFactory"]