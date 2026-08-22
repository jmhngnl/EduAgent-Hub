import pytest

from app.config import Settings
from app.llm import DeterministicEmbeddings
from app.rag import InMemoryKnowledgeStore


@pytest.mark.asyncio
async def test_document_type_filter_and_listing() -> None:
    settings = Settings(
        mock_embeddings=True,
        embedding_dimension=64,
        chunk_size=120,
        chunk_overlap=20,
    )
    store = InMemoryKnowledgeStore(
        DeterministicEmbeddings(settings.embedding_dimension),
        settings,
    )

    await store.ingest_text(
        workspace_id="demo",
        document_id="lab-guide",
        source="实验室服务器指南.md",
        text="GPU 服务器申请需要导师审批。",
        metadata={"document_type": "lab_document"},
    )
    await store.ingest_text(
        workspace_id="demo",
        document_id="paper-001",
        source="FlowMatchingCMR.pdf",
        text="We propose flow matching for cardiac MR image synthesis.",
        metadata={
            "document_type": "paper",
            "year": 2026,
            "venue": "MICCAI",
        },
    )

    lab_results = await store.search(
        workspace_id="demo",
        query="GPU 服务器",
        top_k=5,
        document_type="lab_document",
    )
    paper_results = await store.search(
        workspace_id="demo",
        query="flow matching cardiac MR",
        top_k=5,
        document_type="paper",
    )

    assert {item.document_id for item in lab_results} == {"lab-guide"}
    assert {item.document_id for item in paper_results} == {"paper-001"}

    papers = await store.list_documents(
        workspace_id="demo",
        document_type="paper",
    )
    assert len(papers) == 1
    assert papers[0].document_id == "paper-001"
    assert papers[0].document_type == "paper"
    assert papers[0].chunk_count == 1


@pytest.mark.asyncio
async def test_legacy_document_defaults_to_lab_document() -> None:
    settings = Settings(
        mock_embeddings=True,
        embedding_dimension=64,
        chunk_size=120,
        chunk_overlap=20,
    )
    store = InMemoryKnowledgeStore(
        DeterministicEmbeddings(settings.embedding_dimension),
        settings,
    )
    await store.ingest_text(
        workspace_id="demo",
        document_id="legacy",
        source="legacy.md",
        text="旧版实验室管理文档。",
        metadata={},
    )

    lab_results = await store.search(
        workspace_id="demo",
        query="实验室管理",
        top_k=5,
        document_type="lab_document",
    )
    paper_results = await store.search(
        workspace_id="demo",
        query="实验室管理",
        top_k=5,
        document_type="paper",
    )

    assert [item.document_id for item in lab_results] == ["legacy"]
    assert paper_results == []
