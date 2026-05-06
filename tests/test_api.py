import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent.api.main import app
from agent.db.models import Base, ResearchSession
from agent.db.session import get_session
from agent.llm.openrouter import OpenRouterError

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_serves_web_ui():
    response = client.get("/")

    assert response.status_code == 200
    assert "AI Research Agent" in response.text
    assert 'data-testid="question-input"' in response.text


def test_research_endpoint():
    mock_result = {
        "question": "test question",
        "search_queries": ["q1"],
        "core_entities": ["test"],
        "arxiv_results": [],
        "web_results": [],
        "synthesis": "Test summary",
        "key_findings": ["Finding"],
        "sources": [{"title": "Example", "url": "https://example.com", "source_type": "web"}],
        "session_id": "test-123",
        "duration_seconds": 1.0,
        "tool_errors": [],
        "scraped_content": [],
    }
    with patch("agent.api.main.research_graph") as mock_graph:
        mock_graph.invoke.return_value = mock_result
        response = client.post("/research", json={"question": "test question"})

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Test summary"
    assert data["session_id"] == "test-123"
    assert data["key_findings"] == ["Finding"]
    assert data["search_queries"] == ["q1"]
    assert data["core_entities"] == ["test"]
    assert data["duration_seconds"] == 1.0
    assert data["sources"][0]["title"] == "Example"
    assert data["tool_errors"] == []


def test_research_endpoint_returns_502_for_openrouter_errors():
    with patch("agent.api.main.research_graph") as mock_graph:
        mock_graph.invoke.side_effect = OpenRouterError("OpenRouter failed")
        response = client.post("/research", json={"question": "test question"})

    assert response.status_code == 502
    assert response.json()["detail"] == "OpenRouter failed"


def test_sessions_endpoints_return_persisted_records():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session_id = "00000000-0000-0000-0000-000000000001"

    with test_session_local() as session:
        session.add(
            ResearchSession(
                id=uuid.UUID(session_id),
                question="Stored question",
                summary="Stored summary",
                key_findings=["Stored finding"],
                sources=[{"title": "Stored source", "url": "https://example.com"}],
                search_queries=["stored query"],
                core_entities=["Stored"],
                tool_errors=[{"tool": "arxiv", "query": "q1", "error": "failed"}],
                arxiv_count=1,
                web_count=2,
                duration_seconds=3.5,
            )
        )
        session.commit()

    def override_get_session():
        with test_session_local() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        list_response = client.get("/sessions")
        detail_response = client.get(f"/sessions/{session_id}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()[0]["question"] == "Stored question"
    assert list_response.json()[0]["search_queries"] == ["stored query"]
    assert list_response.json()[0]["core_entities"] == ["Stored"]
    assert detail_response.status_code == 200
    assert detail_response.json()["summary"] == "Stored summary"
    assert detail_response.json()["key_findings"] == ["Stored finding"]
    assert detail_response.json()["tool_errors"][0]["tool"] == "arxiv"
