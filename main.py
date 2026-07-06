"""Minimal project entrypoint for the Modular RAG MCP Server."""

from core.settings import SettingsError, load_settings
from observability.logger import get_logger


logger = get_logger(__name__)


def main() -> int:
    """Load configuration and run the placeholder entrypoint."""
    try:
        settings = load_settings()
    except SettingsError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    logger.info("Loaded settings for LLM provider: %s", settings.llm.provider)
    print("Modular RAG MCP Server configuration is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
