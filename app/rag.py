from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Settings

logger = logging.getLogger(__name__)


def _sanitize_text_for_storage(text: str) -> str:
    """Remove characters PostgreSQL text/jsonb cannot represent safely.

    PDF text extraction can occasionally contain the NUL character (``\\x00``).
    PostgreSQL UTF-8 ``text`` rejects that character with
    ``CharacterNotInRepertoireError``. Sanitize at the knowledge-store boundary
    so PDF, TXT, Markdown, and direct text ingestion all share the same rule.
    """

    nul_count = text.count("\x00")
    if nul_count:
        logger.warning("Removed %d NUL character(s) before knowledge indexing", nul_count)
    return text.replace("\x00", "")


@dataclass(slots=True)
class RetrievedChunk:
    id: str
    document_id: str
    source: str
    content: str
    score: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class KnowledgeDocument:
    document_id: str
    source: str
    document_type: str
    chunk_count: int
    metadata: dict[str, Any]


def _metadata_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return json.loads(raw or "{}")


def _document_type(metadata: dict[str, Any]) -> str:
    value = metadata.get("document_type")
    return value if value in {"lab_document", "paper"} else "lab_document"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]],
    limit: int,
    constant: int = 60,
) -> list[RetrievedChunk]:
    """Fuse multiple ranked result lists using reciprocal rank fusion."""

    fused_scores: dict[str, float] = {}
    best_items: dict[str, RetrievedChunk] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            fused_scores[item.id] = fused_scores.get(item.id, 0.0) + 1.0 / (
                constant + rank
            )
            best_items[item.id] = item

    ordered_ids = sorted(
        fused_scores,
        key=lambda item_id: fused_scores[item_id],
        reverse=True,
    )[:limit]

    return [
        RetrievedChunk(
            id=best_items[item_id].id,
            document_id=best_items[item_id].document_id,
            source=best_items[item_id].source,
            content=best_items[item_id].content,
            score=fused_scores[item_id],
            metadata=best_items[item_id].metadata,
        )
        for item_id in ordered_ids
    ]


class InMemoryKnowledgeStore:
    """Small fallback store used in CI or when PostgreSQL is unavailable."""

    def __init__(self, embeddings: Embeddings, settings: Settings) -> None:
        self.embeddings = embeddings
        self.settings = settings
        self.rows: list[dict[str, Any]] = []

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def ingest_text(
        self,
        *,
        workspace_id: str,
        document_id: str,
        source: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        text = _sanitize_text_for_storage(text)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
        )
        chunks = [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
        vectors = await self.embeddings.aembed_documents(chunks)

        self.rows = [
            row
            for row in self.rows
            if not (
                row["workspace_id"] == workspace_id
                and row["document_id"] == document_id
            )
        ]
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            self.rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "workspace_id": workspace_id,
                    "document_id": document_id,
                    "source": source,
                    "chunk_index": index,
                    "content": chunk,
                    "metadata": metadata or {},
                    "embedding": vector,
                }
            )
        return len(chunks)

    async def search(
        self,
        *,
        workspace_id: str,
        query: str,
        top_k: int,
        document_id: str | None = None,
        document_type: str | None = None,
    ) -> list[RetrievedChunk]:
        query_vector = await self.embeddings.aembed_query(query)
        query_terms = set(query.lower().split())
        ranked: list[RetrievedChunk] = []

        for row in self.rows:
            if row["workspace_id"] != workspace_id:
                continue
            if document_id is not None and row["document_id"] != document_id:
                continue
            metadata = _metadata_dict(row["metadata"])
            if document_type is not None and _document_type(metadata) != document_type:
                continue
            vector_score = sum(
                a * b for a, b in zip(query_vector, row["embedding"], strict=True)
            )
            lexical_score = sum(
                1 for term in query_terms if term and term in row["content"].lower()
            )
            score = vector_score + lexical_score * 0.1
            ranked.append(
                RetrievedChunk(
                    id=row["id"],
                    document_id=row["document_id"],
                    source=row["source"],
                    content=row["content"],
                    score=float(score),
                    metadata=metadata,
                )
            )

        return sorted(ranked, key=lambda item: item.score, reverse=True)[:top_k]

    async def list_documents(
        self,
        *,
        workspace_id: str,
        document_type: str | None = None,
    ) -> list[KnowledgeDocument]:
        grouped: dict[str, KnowledgeDocument] = {}
        for row in self.rows:
            if row["workspace_id"] != workspace_id:
                continue
            metadata = _metadata_dict(row["metadata"])
            resolved_type = _document_type(metadata)
            if document_type is not None and resolved_type != document_type:
                continue

            document_id = row["document_id"]
            existing = grouped.get(document_id)
            if existing is None:
                grouped[document_id] = KnowledgeDocument(
                    document_id=document_id,
                    source=row["source"],
                    document_type=resolved_type,
                    chunk_count=1,
                    metadata=metadata,
                )
            else:
                existing.chunk_count += 1

        return sorted(
            grouped.values(),
            key=lambda item: (item.document_type, item.source, item.document_id),
        )


class PostgresKnowledgeStore:
    """Tenant-scoped pgvector + PostgreSQL full-text hybrid retrieval."""

    def __init__(self, embeddings: Embeddings, settings: Settings) -> None:
        self.embeddings = embeddings
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=30,
            timeout=5,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()

    async def ping(self) -> bool:
        if self.pool is None:
            return False
        return bool(await self.pool.fetchval("SELECT TRUE"))

    def _require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Knowledge store is not connected")
        return self.pool

    async def ingest_text(
        self,
        *,
        workspace_id: str,
        document_id: str,
        source: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        text = _sanitize_text_for_storage(text)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
        )
        chunks = [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
        if not chunks:
            return 0

        vectors = await self.embeddings.aembed_documents(chunks)
        rows = [
            (
                str(uuid.uuid4()),
                workspace_id,
                document_id,
                source,
                index,
                chunk,
                json.dumps(metadata or {}, ensure_ascii=False),
                _vector_literal(vector),
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]

        pool = self._require_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    DELETE FROM knowledge_chunks
                    WHERE workspace_id = $1 AND document_id = $2
                    """,
                    workspace_id,
                    document_id,
                )
                await connection.executemany(
                    """
                    INSERT INTO knowledge_chunks (
                        id, workspace_id, document_id, source, chunk_index,
                        content, metadata, embedding
                    )
                    VALUES (
                        ($1::text)::uuid, $2, $3, $4, $5, $6, ($7::text)::jsonb, ($8::text)::vector
                    )
                    """,
                    rows,
                )

        return len(chunks)

    @staticmethod
    def _to_chunk(row: asyncpg.Record, score: float) -> RetrievedChunk:
        metadata = _metadata_dict(row["metadata"])
        return RetrievedChunk(
            id=str(row["id"]),
            document_id=row["document_id"],
            source=row["source"],
            content=row["content"],
            score=float(score),
            metadata=metadata,
        )

    async def search(
        self,
        *,
        workspace_id: str,
        query: str,
        top_k: int,
        document_id: str | None = None,
        document_type: str | None = None,
    ) -> list[RetrievedChunk]:
        pool = self._require_pool()
        vector = await self.embeddings.aembed_query(query)
        vector_literal = _vector_literal(vector)
        candidates = max(top_k, self.settings.retrieval_candidate_k)

        vector_rows = await pool.fetch(
            """
            SELECT id, document_id, source, content, metadata,
                   1 - (embedding <=> ($2::text)::vector) AS score
            FROM knowledge_chunks
            WHERE workspace_id = $1
              AND ($4::text IS NULL OR document_id = $4)
              AND (
                  $5::text IS NULL
                  OR COALESCE(metadata->>'document_type', 'lab_document') = $5
              )
            ORDER BY embedding <=> ($2::text)::vector
            LIMIT $3
            """,
            workspace_id,
            vector_literal,
            candidates,
            document_id,
            document_type,
        )

        lexical_rows = await pool.fetch(
            """
            SELECT id, document_id, source, content, metadata,
                   GREATEST(
                       ts_rank_cd(
                           search_vector,
                           websearch_to_tsquery('simple', $2)
                       ),
                       similarity(content, $2)
                   ) AS score
            FROM knowledge_chunks
            WHERE workspace_id = $1
              AND ($4::text IS NULL OR document_id = $4)
              AND (
                  $5::text IS NULL
                  OR COALESCE(metadata->>'document_type', 'lab_document') = $5
              )
              AND (
                  search_vector @@ websearch_to_tsquery('simple', $2)
                  OR similarity(content, $2) > 0.05
                  OR content ILIKE '%' || $2 || '%'
              )
            ORDER BY score DESC
            LIMIT $3
            """,
            workspace_id,
            query,
            candidates,
            document_id,
            document_type,
        )

        vector_ranked = [
            self._to_chunk(row, row["score"] or 0.0) for row in vector_rows
        ]
        lexical_ranked = [
            self._to_chunk(row, row["score"] or 0.0) for row in lexical_rows
        ]

        return reciprocal_rank_fusion(
            [vector_ranked, lexical_ranked],
            limit=top_k,
        )

    async def list_documents(
        self,
        *,
        workspace_id: str,
        document_type: str | None = None,
    ) -> list[KnowledgeDocument]:
        pool = self._require_pool()
        rows = await pool.fetch(
            """
            SELECT
                document_id,
                MIN(source) AS source,
                COUNT(*)::int AS chunk_count,
                (array_agg(metadata ORDER BY chunk_index))[1] AS metadata
            FROM knowledge_chunks
            WHERE workspace_id = $1
              AND (
                  $2::text IS NULL
                  OR COALESCE(metadata->>'document_type', 'lab_document') = $2
              )
            GROUP BY document_id
            ORDER BY MIN(created_at) DESC
            """,
            workspace_id,
            document_type,
        )

        documents: list[KnowledgeDocument] = []
        for row in rows:
            metadata = _metadata_dict(row["metadata"])
            documents.append(
                KnowledgeDocument(
                    document_id=row["document_id"],
                    source=row["source"],
                    document_type=_document_type(metadata),
                    chunk_count=row["chunk_count"],
                    metadata=metadata,
                )
            )
        return documents


KnowledgeStore = PostgresKnowledgeStore | InMemoryKnowledgeStore
