import uuid
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent.db.models import Base, ResearchSession
from agent.nodes import (
    plan_searches,
    save_to_db_node,
    scrape_urls_node,
    search_arxiv_node,
    search_web_node,
    synthesize_node,
)


def test_plan_searches_returns_queries():
    llm_json = (
        '{"queries": ["query 1", "query 2", "query 3"], '
        '"core_entities": ["RAG"], "use_arxiv": true}'
    )
    with patch("agent.nodes.chat_completion", return_value=llm_json):
        state = {"question": "What are RAG benchmarks?", "search_queries": [], "session_id": ""}
        result = plan_searches(state)

    assert len(result["search_queries"]) <= 3
    assert all(isinstance(query, str) for query in result["search_queries"])
    assert result["core_entities"] == ["RAG"]
    assert result["use_arxiv"] is True
    assert result["session_id"]


def test_plan_searches_keeps_model_source_choice_for_general_questions():
    llm_json = (
        '{"queries": ["Sam Altman biography", "Sam Altman OpenAI"], '
        '"core_entities": ["Sam Altman"], "use_arxiv": true}'
    )
    with patch("agent.nodes.chat_completion", return_value=llm_json):
        state = {"question": "Who is Sam Altman?", "search_queries": [], "session_id": ""}
        result = plan_searches(state)

    assert result["search_queries"] == ["Sam Altman biography", "Sam Altman OpenAI"]
    assert result["core_entities"] == ["Sam Altman"]
    assert result["use_arxiv"] is True


def test_plan_searches_splits_concatenated_free_model_queries():
    with patch(
        "agent.nodes.chat_completion",
        return_value="Sam Altman biographyWho is Sam Altman\nSam Altman OpenAI",
    ):
        state = {"question": "Who is Sam Altman?", "search_queries": [], "session_id": ""}
        result = plan_searches(state)

    assert result["search_queries"] == [
        "Sam Altman biography",
        "Who is Sam Altman",
        "Sam Altman OpenAI",
    ]


def test_plan_searches_recovers_fields_from_malformed_json_plan():
    malformed_json = """
    {
      "queries": [
        "Andrey Karpaty",
        "Andrej Karpathy biography"
      ],
      "core_entities": [
        "Andrey Karpaty"
      ],
      "use_arxiv": false,
    """
    with patch("agent.nodes.chat_completion", return_value=malformed_json):
        state = {"question": "Who is Andrey Karpaty?", "search_queries": [], "session_id": ""}
        result = plan_searches(state)

    assert result["search_queries"] == ["Andrey Karpaty", "Andrej Karpathy biography"]
    assert result["core_entities"] == ["Andrey Karpaty"]
    assert result["use_arxiv"] is False


def test_plan_searches_filters_question_words_from_fallback_entities():
    with patch("agent.nodes.chat_completion", return_value="not json"):
        state = {"question": "Who is Andrey Karpaty?", "search_queries": [], "session_id": ""}
        result = plan_searches(state)

    assert result["core_entities"] == ["Andrey Karpaty"]


def test_search_arxiv_node_empty_queries():
    state = {
        "question": "test",
        "search_queries": [],
        "arxiv_results": [],
    }
    result = search_arxiv_node(state)
    assert result["arxiv_results"] == []


def test_search_arxiv_node_skips_when_plan_disables_arxiv():
    state = {
        "question": "Who is Sam Altman?",
        "search_queries": ["Sam Altman biography"],
        "use_arxiv": False,
        "arxiv_results": [],
    }

    with patch("agent.nodes.search_arxiv") as mock_search:
        result = search_arxiv_node(state)

    mock_search.assert_not_called()
    assert result["arxiv_results"] == []


def test_search_arxiv_node_records_tool_errors_without_crashing():
    state = {
        "question": "What is Hermes Agent?",
        "search_queries": ["Hermes Agent paper"],
        "use_arxiv": True,
        "tool_errors": [],
    }

    with patch("agent.nodes.search_arxiv", side_effect=RuntimeError("arXiv search failed")):
        result = search_arxiv_node(state)

    assert result["arxiv_results"] == []
    assert result["tool_errors"] == [
        {"tool": "arxiv", "query": "Hermes Agent paper", "error": "arXiv search failed"}
    ]


def test_search_arxiv_node_filters_irrelevant_acronym_matches():
    state = {
        "question": "Who is Sam Altman?",
        "core_entities": ["Sam Altman"],
        "search_queries": ["Sam Altman biography", "Sam Altman OpenAI"],
        "use_arxiv": True,
    }
    arxiv_results = [
        {
            "title": "Deep learning universal crater detection using Segment Anything Model (SAM)",
            "summary": "A paper about SAM for crater detection.",
            "url": "https://arxiv.org/abs/2304.07764",
        },
        {
            "title": "PA-SAM: Prompt Adapter SAM for High-Quality Image Segmentation",
            "summary": "A paper about image segmentation.",
            "url": "https://arxiv.org/abs/2401.13051",
        },
    ]

    with patch("agent.nodes.search_arxiv", return_value=arxiv_results):
        result = search_arxiv_node(state)

    assert result["arxiv_results"] == []


def test_search_web_node_keeps_relevant_results():
    state = {
        "question": "Who is Sam Altman?",
        "core_entities": ["Sam Altman"],
        "search_queries": ["Sam Altman biography", "Sam Altman OpenAI"],
    }
    web_results = [
        {
            "title": "Sam Altman - Wikipedia",
            "snippet": "Samuel Harris Altman is an American entrepreneur and CEO of OpenAI.",
            "url": "https://en.wikipedia.org/wiki/Sam_Altman",
        },
        {
            "title": "Segment Anything Model",
            "snippet": "SAM is an image segmentation model.",
            "url": "https://example.com/sam-model",
        },
    ]

    with patch("agent.nodes.search_web", return_value=web_results):
        result = search_web_node(state)

    assert result["web_results"] == [web_results[0]]


def test_search_web_node_handles_minor_name_misspellings():
    state = {
        "question": "Who is Andrey Karpaty?",
        "core_entities": ["Andrey Karpaty"],
        "search_queries": ["Andrey Karpaty biography"],
    }
    web_results = [
        {
            "title": "Andrej Karpathy - Wikipedia",
            "snippet": "Andrej Karpathy is a computer scientist known for AI and deep learning.",
            "url": "https://en.wikipedia.org/wiki/Andrej_Karpathy",
        }
    ]

    with patch("agent.nodes.search_web", return_value=web_results):
        result = search_web_node(state)

    assert result["web_results"] == web_results


def test_search_web_node_uses_core_entities_before_long_queries():
    state = {
        "question": "Who is Sam Altman?",
        "core_entities": ["Sam Altman"],
        "search_queries": ["Sam Altman's biography and career timeline"],
    }
    calls = []

    def fake_search(query, max_results):
        calls.append(query)
        if query == "Sam Altman":
            return [
                {
                    "title": "Sam Altman",
                    "snippet": "Sam Altman is an entrepreneur and OpenAI leader.",
                    "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                }
            ]
        return []

    with patch("agent.nodes.search_web", side_effect=fake_search):
        result = search_web_node(state)

    assert calls[0] == "Sam Altman"
    assert result["web_results"][0]["title"] == "Sam Altman"


def test_scrape_urls_node_scrapes_top_web_results():
    state = {
        "web_results": [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
            {"url": "https://example.com/3"},
            {"url": "https://example.com/4"},
        ]
    }

    with patch("agent.nodes.scrape", side_effect=lambda url: {"url": url, "content": "content"}):
        result = scrape_urls_node(state)

    assert [item["url"] for item in result["scraped_content"]] == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]


def test_synthesize_node_returns_structured_summary():
    state = {
        "question": "What is RAG?",
        "session_id": "00000000-0000-0000-0000-000000000001",
        "arxiv_results": [
            {
                "title": "RAG Paper",
                "summary": "Academic insight",
                "url": "https://arxiv.org/abs/1",
            }
        ],
        "web_results": [
            {
                "title": "RAG Blog",
                "snippet": "Web insight",
                "url": "https://example.com/rag",
            }
        ],
        "scraped_content": [{"url": "https://example.com/rag", "content": "Longer page text"}],
    }
    llm_json = """
    {
      "key_findings": ["Finding one", "Finding two"],
      "summary": "Structured summary",
      "cited_sources": [
        {
          "title": "RAG Paper",
          "url": "https://arxiv.org/abs/1",
          "source_type": "arxiv",
          "insight": "Academic insight"
        }
      ]
    }
    """

    with patch("agent.nodes.chat_completion", return_value=llm_json):
        result = synthesize_node(state)

    assert result["synthesis"] == "Structured summary"
    assert result["key_findings"] == ["Finding one", "Finding two"]
    assert result["sources"][0]["title"] == "RAG Paper"
    assert result["sources"][0]["url"] == "https://arxiv.org/abs/1"


def test_synthesize_node_does_not_answer_without_sources():
    state = {
        "question": "Who is Sam Altman?",
        "session_id": "00000000-0000-0000-0000-000000000001",
        "arxiv_results": [],
        "web_results": [],
        "scraped_content": [],
    }

    with patch("agent.nodes.chat_completion") as mock_chat:
        result = synthesize_node(state)

    mock_chat.assert_not_called()
    assert result["sources"] == []
    assert result["key_findings"] == []
    assert "No relevant sources" in result["synthesis"]


def test_save_to_db_node_persists_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("agent.nodes.SessionLocal", test_session_local)

    state = {
        "question": "test question",
        "synthesis": "summary",
        "key_findings": ["finding"],
        "sources": [{"title": "Example", "url": "https://example.com"}],
        "search_queries": ["q1"],
        "core_entities": ["Example"],
        "tool_errors": [{"tool": "arxiv", "query": "q1", "error": "failed"}],
        "arxiv_results": [{"url": "arxiv"}],
        "web_results": [{"url": "web"}],
        "session_id": "00000000-0000-0000-0000-000000000001",
        "duration_seconds": 0.5,
    }

    result = save_to_db_node(state)

    with test_session_local() as session:
        record = session.get(ResearchSession, uuid.UUID(result["session_id"]))

    assert record is not None
    assert record.question == "test question"
    assert record.key_findings == ["finding"]
    assert record.sources[0]["title"] == "Example"
    assert record.core_entities == ["Example"]
    assert record.tool_errors[0]["tool"] == "arxiv"
