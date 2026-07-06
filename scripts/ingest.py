"""Offline ingestion CLI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from core.settings import DEFAULT_SETTINGS_PATH, Settings, SettingsError, load_settings  # noqa: E402
from ingestion import IngestionPipeline, IngestionResult  # noqa: E402


SettingsLoader = Callable[[str | Path], Settings]
PipelineFactory = Callable[[Settings, str, Callable[[str, dict[str, Any]], None]], IngestionPipeline]


def main(
    argv: Sequence[str] | None = None,
    settings_loader: SettingsLoader = load_settings,
    pipeline_factory: PipelineFactory | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    source_path = Path(args.path)
    if not source_path.exists():
        parser.error(f"--path does not exist: {source_path}")

    try:
        settings = settings_loader(args.settings)
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    files = _discover_files(source_path)
    if not files:
        print(f"No PDF files found under: {source_path}", file=sys.stderr)
        return 1

    factory = pipeline_factory or _default_pipeline_factory
    pipeline = factory(settings, args.collection, _print_progress)
    results: list[IngestionResult] = []
    for file_path in files:
        print(f"ingest: {file_path}")
        results.append(pipeline.ingest(file_path, force=args.force))

    ingested_count = sum(1 for result in results if not result.skipped)
    skipped_count = sum(1 for result in results if result.skipped)
    chunk_count = sum(len(result.chunks) for result in results)
    vector_count = sum(result.vector_upsert_count for result in results)
    bm25_count = sum(result.bm25_upsert_count for result in results)
    print(
        "summary: "
        f"files={len(files)} ingested={ingested_count} skipped={skipped_count} "
        f"chunks={chunk_count} vector_upserts={vector_count} bm25_upserts={bm25_count}"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest PDF documents into the local RAG indexes.")
    parser.add_argument("--path", required=True, help="PDF file or directory containing PDF files to ingest.")
    parser.add_argument("--collection", default="default", help="Collection name for image/index metadata.")
    parser.add_argument("--force", action="store_true", help="Re-ingest files even when integrity history says they are unchanged.")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_PATH, help="Path to settings YAML.")
    return parser


def _discover_files(source_path: Path) -> list[Path]:
    if source_path.is_file():
        return [source_path] if source_path.suffix.lower() == ".pdf" else []
    return sorted(path for path in source_path.rglob("*.pdf") if path.is_file())


def _default_pipeline_factory(
    settings: Settings,
    collection: str,
    on_progress: Callable[[str, dict[str, Any]], None],
) -> IngestionPipeline:
    return IngestionPipeline(settings=settings, collection=collection, on_progress=on_progress)


def _print_progress(stage: str, payload: dict[str, Any]) -> None:
    status = payload.get("status")
    if status:
        print(f"  {stage}: {status}")
    elif stage == "skipped":
        print("  skipped: unchanged")


if __name__ == "__main__":
    raise SystemExit(main())