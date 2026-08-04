CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(1536) NOT NULL,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', COALESCE(content, ''))
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_workspace_document
    ON knowledge_chunks (workspace_id, document_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_search_vector
    ON knowledge_chunks USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_knowledge_content_trgm
    ON knowledge_chunks USING GIN (content gin_trgm_ops);
