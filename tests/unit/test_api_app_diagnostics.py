from fastapi.testclient import TestClient

from backend.api import app as app_module


client = TestClient(app_module.app)


def test_health_dependencies_has_expected_shape():
    response = client.get("/health/dependencies")
    assert response.status_code == 200

    payload = response.json()
    assert "status" in payload
    assert "checks" in payload
    assert "note" in payload

    checks = payload["checks"]
    assert "groq_api_key_configured" in checks
    assert "postgres_url_configured" in checks
    assert "mongo_url_configured" in checks
    assert "llm_model" in checks
    assert "embedding_model_name" in checks


def test_chat_connection_error_returns_actionable_hint(monkeypatch):
    def raise_connection_error(*args, **kwargs):
        raise Exception("Connection error.")

    monkeypatch.setattr(app_module.agent, "invoke", raise_connection_error)

    response = client.post("/chat", json={"question": "test"})
    assert response.status_code == 500

    detail = response.json()["detail"]
    assert "LLM provider connection failed" in detail
    assert "GROQ_API_KEY" in detail


def test_build_agent_error_detail_falls_back_to_raw_message():
    detail = app_module._build_agent_error_detail(Exception("Something else broke"))
    assert detail == "Agent error: Something else broke"
