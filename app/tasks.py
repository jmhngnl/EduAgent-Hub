from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import asyncpg
from celery import Celery
from pypdf import PdfReader

from app.config import get_settings
from app.llm import ModelFactory
from app.rag import PostgresKnowledgeStore

settings = get_settings()

celery_app = Celery(
    "eduagent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {suffix}")


async def _ingest_file(
    *,
    file_path: str,
    workspace_id: str,
    document_id: str,
    source: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    path = Path(file_path)
    text = extract_text(path)
    if not text.strip():
        raise ValueError("No extractable text found in the uploaded document")

    store = PostgresKnowledgeStore(ModelFactory(settings).embeddings(), settings)
    indexed = False
    await store.connect()
    try:
        count = await store.ingest_text(
            workspace_id=workspace_id,
            document_id=document_id,
            source=source,
            text=text,
            metadata=metadata,
        )
        indexed = True
    finally:
        await store.close()
        if indexed:
            path.unlink(missing_ok=True)

    return {
        "document_id": document_id,
        "chunks_indexed": count,
        "status": "indexed",
    }


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError, OSError, asyncpg.PostgresConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def ingest_file_task(
    self,
    *,
    file_path: str,
    workspace_id: str,
    document_id: str,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotent because ingest replaces chunks for workspace/document_id."""

    return asyncio.run(
        _ingest_file(
            file_path=file_path,
            workspace_id=workspace_id,
            document_id=document_id,
            source=source,
            metadata=metadata or {},
        )
    )
