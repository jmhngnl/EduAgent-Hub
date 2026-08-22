import pytest

from app.config import Settings
from app.llm import DeterministicEmbeddings
from app.rag import InMemoryKnowledgeStore, _sanitize_text_for_storage


def test_sanitize_text_removes_postgres_nul_only() -> None:
    raw = "MIND method\x00Table 1\nAblation\x00Conclusion"

    cleaned = _sanitize_text_for_storage(raw)

    assert cleaned == "MIND methodTable 1\nAblationConclusion"
    assert "\x00" not in cleaned


def test_sanitize_text_is_noop_for_normal_text() -> None:
    raw = "医学图像融合 / Diffusion Transformer / Table 4"

    assert _sanitize_text_for_storage(raw) == raw


@pytest.mark.asyncio
async def test_in_memory_ingestion_sanitizes_extracted_pdf_text() -> None:
    settings = Settings(mock_llm=True, chunk_size=800, chunk_overlap=120)
    store = InMemoryKnowledgeStore(
        DeterministicEmbeddings(dimension=128),
        settings,
    )

    await store.ingest_text(
        workspace_id="demo",
        document_id="paper-with-nul",
        source="paper.pdf",
        text="Abstract\x00 Method\x00 Results and ablation study.",
        metadata={"document_type": "paper"},
    )

