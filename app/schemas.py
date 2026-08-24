from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentType = Literal["lab_document", "paper"]
TaskRoute = Literal["lab_resource", "paper_reading", "general"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
    database: str
    redis: str
    timestamp: datetime


class PlatformStatusResponse(BaseModel):
    service: str
    environment: str
    auth_enabled: bool
    llm_mode: Literal["mock", "remote"]
    llm_provider: str
    llm_model: str
    llm_configured: bool
    embeddings_mode: Literal["deterministic", "remote"]
    embedding_model: str
    embedding_configured: bool


class TextIngestRequest(BaseModel):
    workspace_id: str = Field(default="demo", min_length=1, max_length=100)
    document_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1)
    document_type: DocumentType = "lab_document"
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    status: Literal["indexed", "queued"] = "indexed"
    task_id: str | None = None
    document_type: DocumentType = "lab_document"


class SearchResult(BaseModel):
    id: str
    document_id: str
    source: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    workspace_id: str
    results: list[SearchResult]


class DocumentSummary(BaseModel):
    document_id: str
    source: str
    document_type: DocumentType
    chunk_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentListResponse(BaseModel):
    workspace_id: str
    document_type: DocumentType | None = None
    documents: list[DocumentSummary]


class Citation(BaseModel):
    document_id: str
    source: str
    chunk_id: str
    score: float
    citation_type: Literal["knowledge", "paper"] = "knowledge"
    url: str | None = None
    title: str | None = None
    year: int | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1, max_length=200)
    workspace_id: str = Field(default="demo", min_length=1, max_length=100)


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    task_route: TaskRoute = "general"
    task_route_label: str = "通用任务"
    skill: str | None = None
    guarded: bool = False


class IntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)


class IntentResult(BaseModel):
    intent: Literal[
        "knowledge_question",
        "calculation",
        "task_planning",
        "document_summary",
        "other",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    requires_tool: bool
    suggested_tool: str | None = None
    reason: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    result: Any | None = None
