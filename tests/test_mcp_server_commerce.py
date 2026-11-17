"""Regression tests for the commerce MCP ``list_collections`` tool."""
from pathlib import Path

import pytest

from src.commerce.corpus import CommerceCorpus
from src.mcp_server.commerce_server import build_commerce_protocol
from src.mcp_server.protocol_handler import ProtocolHandler

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "commerce"


@pytest.fixture
def corpus():
    return CommerceCorpus(ROOT, "demo-tenant", load_vectors=False)


@pytest.mark.asyncio
async def test_list_collections_include_stats_passthrough(corpus, monkeypatch):
    """``include_stats`` must be forwarded to the corpus listing call."""
    calls = []

    def fake_list_collections(include_stats=False):
        calls.append(include_stats)
        return {"schema_version": "commerce-collections-v1", "tenant_id": corpus.tenant_id,
            "corpus_version": corpus.corpus_version,
            "collections": [{"name": "livestream-commerce"}]}

    monkeypatch.setattr(corpus, "list_collections", fake_list_collections)
    protocol = build_commerce_protocol(corpus)

    result = await protocol.execute_tool("list_collections", {"include_stats": True})
    assert calls == [True]
    assert result.isError is False
    assert result.structuredContent["collections"] == [{"name": "livestream-commerce"}]

    result_false = await protocol.execute_tool("list_collections", {"include_stats": False})
    assert calls == [True, False]
    assert "stats" not in result_false.structuredContent["collections"][0]

    result_omitted = await protocol.execute_tool("list_collections", {})
    assert calls == [True, False, False]


@pytest.mark.asyncio
async def test_list_collections_include_stats_populates_corpus_stats(corpus):
    """Stats must come from the corpus layer and not be a stub."""
    corpus.vectors = {"vectors": {k: [] for k in list(corpus.records)[:7]}}
    protocol = build_commerce_protocol(corpus)

    result = await protocol.execute_tool("list_collections", {"include_stats": True})
    data = result.structuredContent

    assert data["schema_version"] == "commerce-collections-v1"
    assert data["tenant_id"] == "demo-tenant"
    assert data["corpus_version"] == corpus.corpus_version
    stats = data["collections"][0]["stats"]
    assert stats["document_count"] == 52
    assert stats["section_count"] == 208
    assert stats["vector_count"] == 7


@pytest.mark.asyncio
async def test_list_collections_defaults_to_stats_free_payload(corpus):
    protocol = build_commerce_protocol(corpus)

    result = await protocol.execute_tool("list_collections", {})
    data = result.structuredContent

    assert data["schema_version"] == "commerce-collections-v1"
    assert "stats" not in data["collections"][0]


@pytest.mark.asyncio
async def test_list_collections_schema_does_not_accept_tenant_or_root(corpus):
    protocol = build_commerce_protocol(corpus)

    tools = protocol.get_tool_schemas()
    tool = next(tool for tool in tools if tool.name == "list_collections")
    assert "tenant_id" not in tool.inputSchema["properties"]
    assert "corpus_root" not in tool.inputSchema["properties"]
