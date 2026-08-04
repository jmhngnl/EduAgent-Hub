from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.agent import safe_calculate
from app.config import get_settings
from app.llm import ModelFactory
from app.rag import InMemoryKnowledgeStore, PostgresKnowledgeStore

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP("EduAgent Hub")
settings = get_settings()
_store: PostgresKnowledgeStore | InMemoryKnowledgeStore | None = None
_store_lock = asyncio.Lock()


async def get_store() -> PostgresKnowledgeStore | InMemoryKnowledgeStore:
    global _store
    if _store is not None:
        return _store

    async with _store_lock:
        if _store is not None:
            return _store

        embeddings = ModelFactory(settings).embeddings()
        postgres = PostgresKnowledgeStore(embeddings, settings)
        try:
            await postgres.connect()
            await postgres.ping()
            _store = postgres
        except Exception:
            logger.exception("PostgreSQL unavailable; MCP uses in-memory fallback")
            fallback = InMemoryKnowledgeStore(embeddings, settings)
            await fallback.connect()
            _store = fallback
        return _store


@mcp.tool()
async def search_knowledge(
    query: str,
    top_k: int = 6,
) -> str:
    """Search tenant-scoped educational documents and return grounded passages.

    Args:
        query: Natural-language search query.
        top_k: Number of passages to return, from 1 to 10.

    The process is pinned to DEFAULT_WORKSPACE_ID so the model cannot select
    another tenant through tool arguments.
    """
    top_k = max(1, min(top_k, 10))
    store = await get_store()
    results = await store.search(
        workspace_id=settings.default_workspace_id,
        query=query,
        top_k=top_k,
    )
    return json.dumps(
        [
            {
                "source": item.source,
                "document_id": item.document_id,
                "content": item.content,
                "score": item.score,
            }
            for item in results
        ],
        ensure_ascii=False,
    )


@mcp.tool()
def safe_calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression without executing arbitrary code."""
    return str(safe_calculate(expression))


@mcp.tool()
async def platform_health() -> dict[str, Any]:
    """Return MCP server and knowledge-store health information."""
    store = await get_store()
    return {
        "service": settings.app_name,
        "environment": settings.environment,
        "knowledge_store_ready": await store.ping(),
        "mock_llm": settings.mock_llm,
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
