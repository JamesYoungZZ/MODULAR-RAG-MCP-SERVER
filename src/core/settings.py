"""Configuration loading and validation for the project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SETTINGS_PATH = Path("config/settings.yaml")


class SettingsError(ValueError):
    """Raised when settings cannot be loaded or validated."""


@dataclass(frozen=True)
class ProviderModelSettings:
    provider: str
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    azure_endpoint: str | None = None
    deployment_name: str | None = None
    api_version: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    dimensions: int | None = None


@dataclass(frozen=True)
class VectorStoreSettings:
    backend: str
    persist_path: str


@dataclass(frozen=True)
class SplitterSettings:
    strategy: str
    chunk_size: int
    chunk_overlap: int


@dataclass(frozen=True)
class RetrievalSettings:
    sparse_backend: str
    fusion_algorithm: str
    top_k_dense: int
    top_k_sparse: int
    top_k_final: int


@dataclass(frozen=True)
class RerankSettings:
    backend: str
    model: str | None = None
    top_m: int | None = None


@dataclass(frozen=True)
class EvaluationSettings:
    backends: list[str]
    golden_test_set: str


@dataclass(frozen=True)
class ObservabilitySettings:
    enabled: bool
    log_file: str


@dataclass(frozen=True)
class DashboardSettings:
    enabled: bool
    port: int
    traces_dir: str
    auto_refresh: bool
    refresh_interval: int


@dataclass(frozen=True)
class Settings:
    llm: ProviderModelSettings
    embedding: ProviderModelSettings
    splitter: SplitterSettings
    vector_store: VectorStoreSettings
    retrieval: RetrievalSettings
    rerank: RerankSettings
    evaluation: EvaluationSettings
    observability: ObservabilitySettings
    vision_llm: ProviderModelSettings | None = None
    dashboard: DashboardSettings | None = None


def load_settings(path: str | Path = DEFAULT_SETTINGS_PATH) -> Settings:
    """Load YAML settings from disk and validate required fields."""
    settings_path = Path(path)
    try:
        raw_data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"Settings file not found: {settings_path}") from exc
    except yaml.YAMLError as exc:
        raise SettingsError(f"Invalid YAML in settings file: {settings_path}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise SettingsError("Settings file must contain a YAML mapping at the top level")

    settings = _settings_from_mapping(raw_data)
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    """Validate required settings fields and report paths in error messages."""
    required_values: dict[str, Any] = {
        "llm.provider": settings.llm.provider,
        "embedding.provider": settings.embedding.provider,
        "splitter.strategy": settings.splitter.strategy,
        "splitter.chunk_size": settings.splitter.chunk_size,
        "splitter.chunk_overlap": settings.splitter.chunk_overlap,
        "vector_store.backend": settings.vector_store.backend,
        "vector_store.persist_path": settings.vector_store.persist_path,
        "retrieval.sparse_backend": settings.retrieval.sparse_backend,
        "retrieval.fusion_algorithm": settings.retrieval.fusion_algorithm,
        "retrieval.top_k_dense": settings.retrieval.top_k_dense,
        "retrieval.top_k_sparse": settings.retrieval.top_k_sparse,
        "retrieval.top_k_final": settings.retrieval.top_k_final,
        "rerank.backend": settings.rerank.backend,
        "evaluation.backends": settings.evaluation.backends,
        "evaluation.golden_test_set": settings.evaluation.golden_test_set,
        "observability.enabled": settings.observability.enabled,
        "observability.log_file": settings.observability.log_file,
    }

    missing_paths = [path for path, value in required_values.items() if _is_missing(value)]
    if missing_paths:
        raise SettingsError("Missing required settings fields: " + ", ".join(missing_paths))


def _settings_from_mapping(raw_data: dict[str, Any]) -> Settings:
    return Settings(
        llm=_provider_model_settings(raw_data, "llm"),
        embedding=_provider_model_settings(raw_data, "embedding"),
        vision_llm=_optional_provider_model_settings(raw_data, "vision_llm"),
        splitter=SplitterSettings(
            strategy=_required_value(raw_data, "splitter.strategy"),
            chunk_size=_required_int(raw_data, "splitter.chunk_size"),
            chunk_overlap=_required_int(raw_data, "splitter.chunk_overlap"),
        ),
        vector_store=VectorStoreSettings(
            backend=_required_value(raw_data, "vector_store.backend"),
            persist_path=_required_value(raw_data, "vector_store.persist_path"),
        ),
        retrieval=RetrievalSettings(
            sparse_backend=_required_value(raw_data, "retrieval.sparse_backend"),
            fusion_algorithm=_required_value(raw_data, "retrieval.fusion_algorithm"),
            top_k_dense=_required_int(raw_data, "retrieval.top_k_dense"),
            top_k_sparse=_required_int(raw_data, "retrieval.top_k_sparse"),
            top_k_final=_required_int(raw_data, "retrieval.top_k_final"),
        ),
        rerank=RerankSettings(
            backend=_required_value(raw_data, "rerank.backend"),
            model=_optional_value(raw_data, "rerank.model"),
            top_m=_optional_int(raw_data, "rerank.top_m"),
        ),
        evaluation=EvaluationSettings(
            backends=_required_list(raw_data, "evaluation.backends"),
            golden_test_set=_required_value(raw_data, "evaluation.golden_test_set"),
        ),
        observability=ObservabilitySettings(
            enabled=_required_bool(raw_data, "observability.enabled"),
            log_file=_required_value(raw_data, "observability.log_file"),
        ),
        dashboard=_optional_dashboard_settings(raw_data),
    )


def _provider_model_settings(raw_data: dict[str, Any], section: str) -> ProviderModelSettings:
    return ProviderModelSettings(
        provider=_required_value(raw_data, f"{section}.provider"),
        model=_optional_value(raw_data, f"{section}.model"),
        api_key=_optional_value(raw_data, f"{section}.api_key"),
        base_url=_optional_value(raw_data, f"{section}.base_url"),
        azure_endpoint=_optional_value(raw_data, f"{section}.azure_endpoint"),
        deployment_name=_optional_value(raw_data, f"{section}.deployment_name"),
        api_version=_optional_value(raw_data, f"{section}.api_version"),
        temperature=_optional_float(raw_data, f"{section}.temperature"),
        max_tokens=_optional_int(raw_data, f"{section}.max_tokens"),
        dimensions=_optional_int(raw_data, f"{section}.dimensions"),
    )


def _optional_provider_model_settings(raw_data: dict[str, Any], section: str) -> ProviderModelSettings | None:
    if section not in raw_data:
        return None
    return _provider_model_settings(raw_data, section)


def _optional_dashboard_settings(raw_data: dict[str, Any]) -> DashboardSettings | None:
    if "dashboard" not in raw_data:
        return None
    return DashboardSettings(
        enabled=_required_bool(raw_data, "dashboard.enabled"),
        port=_required_int(raw_data, "dashboard.port"),
        traces_dir=_required_value(raw_data, "dashboard.traces_dir"),
        auto_refresh=_required_bool(raw_data, "dashboard.auto_refresh"),
        refresh_interval=_required_int(raw_data, "dashboard.refresh_interval"),
    )


def _required_value(raw_data: dict[str, Any], field_path: str) -> str:
    value = _get_field(raw_data, field_path)
    if _is_missing(value):
        raise SettingsError(f"Missing required settings field: {field_path}")
    if not isinstance(value, str):
        raise SettingsError(f"Settings field {field_path} must be a string")
    return value


def _optional_value(raw_data: dict[str, Any], field_path: str) -> str | None:
    value = _get_field(raw_data, field_path)
    if _is_missing(value):
        return None
    if not isinstance(value, str):
        raise SettingsError(f"Settings field {field_path} must be a string")
    return value


def _required_int(raw_data: dict[str, Any], field_path: str) -> int:
    value = _get_field(raw_data, field_path)
    if _is_missing(value):
        raise SettingsError(f"Missing required settings field: {field_path}")
    if not isinstance(value, int) or isinstance(value, bool):
        raise SettingsError(f"Settings field {field_path} must be an integer")
    return value


def _optional_int(raw_data: dict[str, Any], field_path: str) -> int | None:
    value = _get_field(raw_data, field_path)
    if _is_missing(value):
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise SettingsError(f"Settings field {field_path} must be an integer")
    return value


def _optional_float(raw_data: dict[str, Any], field_path: str) -> float | None:
    value = _get_field(raw_data, field_path)
    if _is_missing(value):
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SettingsError(f"Settings field {field_path} must be a number")
    return float(value)


def _required_bool(raw_data: dict[str, Any], field_path: str) -> bool:
    value = _get_field(raw_data, field_path)
    if _is_missing(value):
        raise SettingsError(f"Missing required settings field: {field_path}")
    if not isinstance(value, bool):
        raise SettingsError(f"Settings field {field_path} must be a boolean")
    return value


def _required_list(raw_data: dict[str, Any], field_path: str) -> list[str]:
    value = _get_field(raw_data, field_path)
    if value is None:
        raise SettingsError(f"Missing required settings field: {field_path}")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SettingsError(f"Settings field {field_path} must be a list of strings")
    return value


def _get_field(raw_data: dict[str, Any], field_path: str) -> Any:
    value: Any = raw_data
    for part in field_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")