from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, AsyncIterator
from urllib.parse import urlparse

from celery.result import AsyncResult
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, StreamingResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis

from app.agent import (
    AgentService,
    InMemoryConversationStore,
    RedisConversationStore,
)
from app.config import Settings, get_settings
from app.llm import ModelFactory
from app.rag import InMemoryKnowledgeStore, PostgresKnowledgeStore
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestResponse,
    IntentRequest,
    IntentResult,
    PlatformStatusResponse,
    SearchResponse,
    SearchResult,
    TaskStatusResponse,
    TextIngestRequest,
)
from app.tasks import celery_app, ingest_file_task

logger = logging.getLogger(__name__)


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def configure_observability(app: FastAPI, settings: Settings) -> None:
    """Configure optional LangSmith and OpenTelemetry tracing."""

    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key

    if not settings.otel_exporter_otlp_endpoint:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "eduagent-hub-api",
                "deployment.environment": settings.environment,
            }
        )
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        )
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


@dataclass(frozen=True, slots=True)
class AuthContext:
    api_key: str | None
    workspace_id: str | None


async def authenticate(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    mappings = settings.parsed_api_key_workspaces
    allowed = settings.parsed_api_keys | set(mappings)

    if not allowed:
        return AuthContext(api_key=None, workspace_id=None)

    if not x_api_key or x_api_key not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )

    return AuthContext(api_key=x_api_key, workspace_id=mappings.get(x_api_key))


def enforce_workspace(auth: AuthContext, requested_workspace_id: str) -> None:
    if auth.workspace_id and auth.workspace_id != requested_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The API key is not authorized for this workspace",
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)

    embeddings = ModelFactory(settings).embeddings()
    postgres_store = PostgresKnowledgeStore(embeddings, settings)
    try:
        await postgres_store.connect()
        await postgres_store.ping()
        knowledge = postgres_store
        app.state.database_status = "connected"
    except Exception:
        logger.exception("PostgreSQL unavailable; using in-memory fallback")
        await postgres_store.close()
        knowledge = InMemoryKnowledgeStore(embeddings, settings)
        await knowledge.connect()
        app.state.database_status = "fallback-memory"

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        conversations = RedisConversationStore(
            redis,
            max_messages=settings.max_history_messages,
        )
        app.state.redis_status = "connected"
    except Exception:
        logger.exception("Redis unavailable; using in-memory conversation store")
        await redis.aclose()
        redis = None
        conversations = InMemoryConversationStore(settings.max_history_messages)
        app.state.redis_status = "fallback-memory"

    app.state.settings = settings
    app.state.knowledge = knowledge
    app.state.redis = redis
    app.state.conversations = conversations
    app.state.agent = AgentService(
        settings=settings,
        knowledge=knowledge,
        conversations=conversations,
    )

    yield

    await knowledge.close()
    if redis is not None:
        await redis.aclose()


app = FastAPI(
    title="EduAgent Hub API",
    version="1.1.0",
    description="Production-oriented LangGraph Agent and hybrid RAG platform.",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app, include_in_schema=False)
configure_observability(app, settings)


@app.get("/health", response_model=HealthResponse, tags=["platform"])
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    database = request.app.state.database_status
    redis_status = request.app.state.redis_status
    overall = (
        "ok"
        if database == "connected" and redis_status == "connected"
        else "degraded"
    )
    return HealthResponse(
        status=overall,
        service=settings.app_name,
        environment=settings.environment,
        database=database,
        redis=redis_status,
        timestamp=datetime.now(UTC),
    )


@app.get(
    "/v1/platform/status",
    response_model=PlatformStatusResponse,
    tags=["platform"],
)
async def platform_status(request: Request) -> PlatformStatusResponse:
    settings: Settings = request.app.state.settings
    provider = settings.llm_provider.strip().lower()
    if not provider or provider == "auto":
        provider = urlparse(settings.llm_base_url).netloc or "custom"
    return PlatformStatusResponse(
        service=settings.app_name,
        environment=settings.environment,
        auth_enabled=bool(settings.parsed_api_keys or settings.parsed_api_key_workspaces),
        llm_mode="mock" if settings.mock_llm else "remote",
        llm_provider=provider,
        llm_model=settings.llm_model,
        llm_configured=settings.mock_llm or bool(settings.llm_api_key),
        embeddings_mode=(
            "deterministic" if settings.mock_embeddings else "remote"
        ),
        embedding_model=settings.embedding_model,
        embedding_configured=(
            settings.mock_embeddings or bool(settings.embedding_api_key)
        ),
    )


@app.post(
    "/v1/knowledge/text",
    response_model=IngestResponse,
    tags=["knowledge"],
)
async def ingest_text(
    request: Request,
    payload: TextIngestRequest,
    auth: Annotated[AuthContext, Depends(authenticate)],
) -> IngestResponse:
    enforce_workspace(auth, payload.workspace_id)
    count = await request.app.state.knowledge.ingest_text(
        workspace_id=payload.workspace_id,
        document_id=payload.document_id,
        source=payload.source,
        text=payload.text,
        metadata=payload.metadata,
    )
    return IngestResponse(
        document_id=payload.document_id,
        chunks_indexed=count,
        status="indexed",
    )


@app.post(
    "/v1/knowledge/files",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["knowledge"],
)
async def ingest_file(
    request: Request,
    auth: Annotated[AuthContext, Depends(authenticate)],
    file: Annotated[UploadFile, File()],
    workspace_id: Annotated[str, Form()] = "demo",
    document_id: Annotated[str | None, Form()] = None,
) -> IngestResponse:
    settings: Settings = request.app.state.settings
    enforce_workspace(auth, workspace_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".txt", ".md", ".markdown"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, TXT and Markdown files are supported",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    resolved_document_id = document_id or str(uuid.uuid4())
    destination = upload_dir / f"{uuid.uuid4().hex}{suffix}"

    max_bytes = settings.max_upload_mb * 1024 * 1024
    bytes_written = 0
    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds {settings.max_upload_mb} MB upload limit",
                    )
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if bytes_written == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    task = ingest_file_task.delay(
        file_path=str(destination),
        workspace_id=workspace_id,
        document_id=resolved_document_id,
        source=file.filename or resolved_document_id,
        metadata={"content_type": file.content_type or "application/octet-stream"},
    )
    return IngestResponse(
        document_id=resolved_document_id,
        chunks_indexed=0,
        status="queued",
        task_id=task.id,
    )


@app.get(
    "/v1/tasks/{task_id}",
    response_model=TaskStatusResponse,
    tags=["knowledge"],
)
async def task_status(
    task_id: str,
    auth: Annotated[AuthContext, Depends(authenticate)],
) -> TaskStatusResponse:
    del auth
    task = AsyncResult(task_id, app=celery_app)
    result = task.result if task.successful() else None
    return TaskStatusResponse(task_id=task_id, state=task.state, result=result)


@app.get(
    "/v1/knowledge/search",
    response_model=SearchResponse,
    tags=["knowledge"],
)
async def search_knowledge(
    request: Request,
    auth: Annotated[AuthContext, Depends(authenticate)],
    query: Annotated[str, Query(min_length=1)],
    workspace_id: str = "demo",
    top_k: Annotated[int, Query(ge=1, le=20)] = 6,
) -> SearchResponse:
    enforce_workspace(auth, workspace_id)
    results = await request.app.state.knowledge.search(
        workspace_id=workspace_id,
        query=query,
        top_k=top_k,
    )
    return SearchResponse(
        query=query,
        workspace_id=workspace_id,
        results=[
            SearchResult(
                id=item.id,
                document_id=item.document_id,
                source=item.source,
                content=item.content,
                score=item.score,
                metadata=item.metadata,
            )
            for item in results
        ],
    )


@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    tags=["agent"],
)
async def chat(
    request: Request,
    payload: ChatRequest,
    auth: Annotated[AuthContext, Depends(authenticate)],
) -> ChatResponse:
    enforce_workspace(auth, payload.workspace_id)
    try:
        return await request.app.state.agent.chat(
            message=payload.message,
            session_id=payload.session_id,
            workspace_id=payload.workspace_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Agent configuration error")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent request failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "Upstream model request failed. Check the server-side LLM_* "
                "configuration and provider account status."
            ),
        ) from exc


@app.post(
    "/v1/chat/stream",
    tags=["agent"],
)
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    auth: Annotated[AuthContext, Depends(authenticate)],
) -> StreamingResponse:
    enforce_workspace(auth, payload.workspace_id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in request.app.state.agent.stream(
            message=payload.message,
            session_id=payload.session_id,
            workspace_id=payload.workspace_id,
        ):
            yield f"event: {event['type']}\n"
            yield "data: " + json.dumps(event["data"], ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/v1/structured/intent",
    response_model=IntentResult,
    tags=["agent"],
)
async def structured_intent(
    request: Request,
    payload: IntentRequest,
    auth: Annotated[AuthContext, Depends(authenticate)],
) -> IntentResult:
    del auth
    factory = ModelFactory(request.app.state.settings)
    return await factory.classify_intent(payload.text)
