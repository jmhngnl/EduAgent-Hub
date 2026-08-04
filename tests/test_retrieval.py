import pytest

from app.config import Settings
from app.llm import DeterministicEmbeddings
from app.rag import InMemoryKnowledgeStore, RetrievedChunk, reciprocal_rank_fusion


def test_reciprocal_rank_fusion_deduplicates_and_reranks() -> None:
    first = [
        RetrievedChunk("a", "doc-a", "a.md", "A", 0.9, {}),
        RetrievedChunk("b", "doc-b", "b.md", "B", 0.8, {}),
    ]
    second = [
        RetrievedChunk("b", "doc-b", "b.md", "B", 0.7, {}),
        RetrievedChunk("c", "doc-c", "c.md", "C", 0.6, {}),
    ]

    result = reciprocal_rank_fusion([first, second], limit=3)

    assert result[0].id == "b"
    assert {item.id for item in result} == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_in_memory_store_is_workspace_scoped() -> None:
    settings = Settings(mock_llm=True, chunk_size=80, chunk_overlap=10)
    store = InMemoryKnowledgeStore(
        DeterministicEmbeddings(dimension=128),
        settings,
    )

    await store.ingest_text(
        workspace_id="workspace-a",
        document_id="policy",
        source="policy.md",
        text="实验室 GPU 申请需要导师审批，并说明预计使用时长。",
    )
    await store.ingest_text(
        workspace_id="workspace-b",
        document_id="secret",
        source="secret.md",
        text="这是另一个租户的数据，不应被检索。",
    )

    results = await store.search(
        workspace_id="workspace-a",
        query="GPU 申请",
        top_k=10,
    )

    assert results
    assert all(item.document_id != "secret" for item in results)
