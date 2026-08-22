from fastapi.testclient import TestClient

from app.main import AuthContext, app, authenticate


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "EduAgent Hub"
    assert body["status"] in {"ok", "degraded"}


def test_text_ingestion_and_mock_chat() -> None:
    app.dependency_overrides[authenticate] = lambda: AuthContext(
        api_key="test-key",
        workspace_id="demo",
    )

    try:
        with TestClient(app) as client:
            ingest = client.post(
                "/v1/knowledge/text",
                json={
                    "workspace_id": "demo",
                    "document_id": "test-policy",
                    "source": "test-policy.md",
                    "text": "GPU 资源申请需要说明用途和预计使用时长，并由导师审批。",
                    "metadata": {
                        "test": True,
                        "document_type": "lab_document",
                    },
                },
            )
            assert ingest.status_code == 200

            chat = client.post(
                "/v1/chat",
                json={
                    "message": "GPU 申请需要什么？",
                    "session_id": "pytest-session",
                    "workspace_id": "demo",
                },
            )

        assert chat.status_code == 200
        payload = chat.json()
        assert "GPU" in payload["answer"]
        assert payload["citations"]
    finally:
        app.dependency_overrides.clear()


def test_workspace_binding_rejects_cross_workspace_access() -> None:
    app.dependency_overrides[authenticate] = lambda: AuthContext(
        api_key="team-a-key",
        workspace_id="team-a",
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/knowledge/search",
                params={"query": "policy", "workspace_id": "team-b"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_platform_status_does_not_expose_secrets() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/platform/status")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_mode"] in {"mock", "remote"}
    assert body["embeddings_mode"] in {"deterministic", "remote"}
    serialized = response.text.lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized
