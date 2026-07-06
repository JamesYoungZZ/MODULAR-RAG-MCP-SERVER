import pytest

from core.settings import (
    EvaluationSettings,
    ObservabilitySettings,
    ProviderModelSettings,
    RerankSettings,
    RetrievalSettings,
    Settings,
    SplitterSettings,
    VectorStoreSettings,
)
from libs.evaluator import BaseEvaluator, CustomEvaluator, EvaluatorFactory


class FakeEvaluator(BaseEvaluator):
    def __init__(self, config: EvaluationSettings) -> None:
        self.config = config

    def evaluate(
        self,
        query: str,
        retrieved_ids: list[str],
        golden_ids: list[str],
        trace: object | None = None,
    ) -> dict[str, float]:
        return {"retrieved_count": float(len(retrieved_ids))}


@pytest.fixture(autouse=True)
def reset_evaluator_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(EvaluatorFactory, "_backends", {"custom": lambda config: CustomEvaluator()})


def test_custom_evaluator_reports_hit_rate_and_mrr_for_first_hit() -> None:
    evaluator = CustomEvaluator()

    metrics = evaluator.evaluate(
        query="What mentions beta?",
        retrieved_ids=["chunk-a", "chunk-b", "chunk-c"],
        golden_ids=["chunk-c", "chunk-z"],
    )

    assert metrics == {"hit_rate": 1.0, "mrr": 1 / 3}


def test_custom_evaluator_reports_zero_metrics_without_hit() -> None:
    evaluator = CustomEvaluator()

    metrics = evaluator.evaluate(query="missing", retrieved_ids=["chunk-a"], golden_ids=["chunk-z"])

    assert metrics == {"hit_rate": 0.0, "mrr": 0.0}


def test_custom_evaluator_reports_zero_metrics_without_golden_ids() -> None:
    evaluator = CustomEvaluator()

    metrics = evaluator.evaluate(query="missing", retrieved_ids=["chunk-a"], golden_ids=[])

    assert metrics == {"hit_rate": 0.0, "mrr": 0.0}


def test_evaluator_factory_returns_enabled_evaluators() -> None:
    settings = _settings_with_evaluation(backends=["custom"])

    evaluators = EvaluatorFactory.create(settings)

    assert len(evaluators) == 1
    assert isinstance(evaluators[0], CustomEvaluator)


def test_evaluator_factory_returns_empty_list_when_no_backends_enabled() -> None:
    settings = _settings_with_evaluation(backends=[])

    assert EvaluatorFactory.create(settings) == []


def test_evaluator_factory_creates_registered_backend() -> None:
    settings = _settings_with_evaluation(backends=["fake"])
    EvaluatorFactory.register_backend("fake", FakeEvaluator)

    evaluators = EvaluatorFactory.create(settings)

    assert isinstance(evaluators[0], FakeEvaluator)
    assert evaluators[0].evaluate("query", ["a", "b"], ["a"]) == {"retrieved_count": 2.0}


def test_evaluator_factory_normalizes_backend_names() -> None:
    settings = _settings_with_evaluation(backends=["  CUSTOM  "])

    evaluators = EvaluatorFactory.create(settings)

    assert isinstance(evaluators[0], CustomEvaluator)


def test_evaluator_factory_rejects_unknown_backend() -> None:
    settings = _settings_with_evaluation(backends=["missing"])

    with pytest.raises(ValueError, match="Unsupported evaluator backend: missing"):
        EvaluatorFactory.create(settings)


def test_evaluator_factory_rejects_empty_backend_registration() -> None:
    with pytest.raises(ValueError, match="Evaluator backend name must not be empty"):
        EvaluatorFactory.register_backend("  ", FakeEvaluator)


def _settings_with_evaluation(backends: list[str]) -> Settings:
    return Settings(
        llm=ProviderModelSettings(provider="placeholder", model="placeholder"),
        embedding=ProviderModelSettings(provider="placeholder", model="placeholder"),
        splitter=SplitterSettings(strategy="recursive", chunk_size=1000, chunk_overlap=200),
        vector_store=VectorStoreSettings(backend="chroma", persist_path="./data/db/chroma"),
        retrieval=RetrievalSettings(
            sparse_backend="bm25",
            fusion_algorithm="rrf",
            top_k_dense=20,
            top_k_sparse=20,
            top_k_final=10,
        ),
        rerank=RerankSettings(backend="none", model=None, top_m=30),
        evaluation=EvaluationSettings(backends=backends, golden_test_set="./tests/fixtures/golden_test_set.json"),
        observability=ObservabilitySettings(enabled=True, log_file="./logs/traces.jsonl"),
    )