from pathlib import Path

import pytest

from core.settings import SettingsError, load_settings


VALID_SETTINGS = """
llm:
  provider: placeholder
  model: placeholder

embedding:
  provider: placeholder
  model: placeholder

vector_store:
  backend: chroma
  persist_path: ./data/db/chroma

retrieval:
  sparse_backend: bm25
  fusion_algorithm: rrf
  top_k_dense: 20
  top_k_sparse: 20
  top_k_final: 10

rerank:
  backend: none
  model: placeholder
  top_m: 30

evaluation:
  backends: []
  golden_test_set: ./tests/fixtures/golden_test_set.json

observability:
  enabled: true
  log_file: ./logs/traces.jsonl
"""


def test_load_settings_returns_typed_settings(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(VALID_SETTINGS, encoding="utf-8")

    settings = load_settings(settings_path)

    assert settings.llm.provider == "placeholder"
    assert settings.embedding.provider == "placeholder"
    assert settings.vector_store.backend == "chroma"
    assert settings.retrieval.top_k_final == 10
    assert settings.rerank.backend == "none"
    assert settings.observability.enabled is True


def test_load_settings_reports_missing_required_field(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        VALID_SETTINGS.replace("  provider: placeholder\n  model: placeholder\n\nvector_store:", "  model: placeholder\n\nvector_store:"),
        encoding="utf-8",
    )

    with pytest.raises(SettingsError, match="embedding.provider"):
        load_settings(settings_path)


def test_load_settings_rejects_invalid_field_type(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(VALID_SETTINGS.replace("top_k_final: 10", "top_k_final: ten"), encoding="utf-8")

    with pytest.raises(SettingsError, match="retrieval.top_k_final"):
        load_settings(settings_path)