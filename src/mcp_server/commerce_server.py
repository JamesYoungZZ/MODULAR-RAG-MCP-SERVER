"""Tenant-bound stdio MCP entry point for commerce documents.

No general collection selection or filesystem access is exposed. Environment
and filesystem permissions are the trust boundary for this local subprocess.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

from mcp import types
from mcp.server.stdio import stdio_server

from src.commerce.corpus import CommerceCorpus
from src.mcp_server.protocol_handler import ProtocolHandler, create_mcp_server


async def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)
    root = Path(os.environ.get("COMMERCE_CORPUS_ROOT", str(Path(__file__).resolve().parents[2] / "fixtures/commerce")))
    tenant = os.environ.get("COMMERCE_TENANT_ID", "demo-tenant")
    corpus = CommerceCorpus(root, tenant)
    embedding = None
    if os.environ.get("COMMERCE_DENSE_ENABLED") == "true":
        if corpus.vectors is None:
            raise ValueError("dense mode requires an explicitly built vectors.json")
        if corpus.vectors["embedding_model"] == "local-all-MiniLM-L6-v2":
            from src.commerce.embedding import LocalCommerceEmbedding
            embedding = LocalCommerceEmbedding()
        else:
            from src.core.settings import load_settings
            from src.libs.embedding.embedding_factory import EmbeddingFactory
            settings = load_settings()
            if corpus.vectors["embedding_model"] != settings.embedding.model:
                raise ValueError("embedding_model_mismatch")
            embedding = EmbeddingFactory.create(settings)
    protocol = ProtocolHandler("commerce-knowledge", "1.0.0")
    lock = asyncio.Lock()

    def result(data):
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
            structuredContent=data, isError=False)

    async def search(query: str, market: str, canonical_product_id: str | None = None, top_k: int = 5):
        async with lock:
            return result(await asyncio.to_thread(corpus.search, query, market, canonical_product_id, top_k, embedding=embedding))

    async def read(section_id: str, market: str, canonical_product_id: str | None = None):
        return result(corpus.read(section_id, market, canonical_product_id))

    output_schema = {"type": "object", "properties": {
        "schema_version": {"const": "commerce-retrieval-v1"},
        "tenant_id": {"type": "string"}, "market": {"enum": ["DE", "FR"]},
        "requested_product_id": {"type": ["string", "null"]},
        "corpus_version": {"type": "string"}, "retrieval_mode": {"type": "string"},
        "degraded": {"type": "boolean"}, "coverage": {"type": "string"},
        "sections": {"type": "array", "maxItems": 8, "items": {"type": "object"}}},
        "required": ["schema_version", "tenant_id", "market", "requested_product_id", "sections", "retrieval_mode", "degraded", "coverage", "corpus_version"],
        "additionalProperties": False}
    scope = {"market": {"type": "string", "enum": ["DE", "FR"]},
        "canonical_product_id": {"type": ["string", "null"], "maxLength": 96}}
    protocol.register_tool("search_commerce_documents", "Retrieve verbatim product/policy sections with scope, version and citations; no generated answer.",
        {"type": "object", "properties": {**scope, "query": {"type": "string", "minLength": 1, "maxLength": 500},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 8}}, "required": ["query", "market"], "additionalProperties": False}, search, output_schema=output_schema)
    protocol.register_tool("read_commerce_section", "Read an exact published section within the same product/market scope.",
        {"type": "object", "properties": {**scope, "section_id": {"type": "string", "maxLength": 180}},
            "required": ["section_id", "market"], "additionalProperties": False}, read, output_schema=output_schema)
    server = create_mcp_server("commerce-knowledge", "1.0.0", protocol_handler=protocol, register_tools=False)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
