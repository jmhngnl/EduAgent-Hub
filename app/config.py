from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "EduAgent Hub"
    environment: str = "development"
    log_level: str = "INFO"

    # Comma-separated API keys. Leave empty only for local development.
    api_keys: str = ""
    # Optional key-to-workspace mapping: "key-a:workspace-a,key-b:workspace-b".
    api_key_workspaces: str = ""

    database_url: str = "postgresql://eduagent:eduagent@postgres:5432/eduagent"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    mock_llm: bool = True
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 2

    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 6
    retrieval_candidate_k: int = 20
    max_history_messages: int = 16
    max_user_input_chars: int = 12_000

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "eduagent-hub"

    otel_exporter_otlp_endpoint: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    upload_dir: str = "/tmp/eduagent_uploads"
    max_upload_mb: int = 30
    default_workspace_id: str = "demo"

    @property
    def parsed_api_keys(self) -> set[str]:
        return {item.strip() for item in self.api_keys.split(",") if item.strip()}

    @property
    def parsed_api_key_workspaces(self) -> dict[str, str]:
        mappings: dict[str, str] = {}
        for item in self.api_key_workspaces.split(","):
            key, separator, workspace = item.strip().partition(":")
            if separator and key and workspace:
                mappings[key] = workspace
        return mappings

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
