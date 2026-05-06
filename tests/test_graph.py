from agent import graph as graph_module


def test_graph_runs_with_mocked_nodes(monkeypatch):
    def fake_plan_searches(state):
        return {"search_queries": ["q1"], "session_id": "00000000-0000-0000-0000-000000000001"}

    def fake_search_arxiv(state):
        return {"arxiv_results": [{"title": "Paper", "summary": "Summary", "url": "arxiv-url"}]}

    def fake_search_web(state):
        return {"web_results": [{"title": "Web", "snippet": "Snippet", "url": "web-url"}]}

    def fake_scrape_urls(state):
        return {"scraped_content": [{"url": "web-url", "content": "Content"}]}

    def fake_synthesize(state):
        return {
            "synthesis": "Synthesis",
            "key_findings": ["Finding"],
            "sources": [{"title": "Paper", "url": "arxiv-url"}],
        }

    def fake_save_to_db(state):
        return {"session_id": state["session_id"]}

    monkeypatch.setattr(graph_module, "plan_searches", fake_plan_searches)
    monkeypatch.setattr(graph_module, "search_arxiv_node", fake_search_arxiv)
    monkeypatch.setattr(graph_module, "search_web_node", fake_search_web)
    monkeypatch.setattr(graph_module, "scrape_urls_node", fake_scrape_urls)
    monkeypatch.setattr(graph_module, "synthesize_node", fake_synthesize)
    monkeypatch.setattr(graph_module, "save_to_db_node", fake_save_to_db)

    graph = graph_module.build_graph()
    result = graph.invoke(
        {
            "question": "test",
            "search_queries": [],
            "core_entities": [],
            "arxiv_results": [],
            "web_results": [],
            "scraped_content": [],
            "synthesis": "",
            "key_findings": [],
            "sources": [],
            "session_id": "",
            "duration_seconds": 0.0,
        }
    )

    assert result["synthesis"] == "Synthesis"
    assert result["key_findings"] == ["Finding"]
    assert result["sources"] == [{"title": "Paper", "url": "arxiv-url"}]


def test_graph_combines_parallel_tool_errors(monkeypatch):
    def fake_plan_searches(state):
        return {
            "search_queries": ["q1"],
            "session_id": "00000000-0000-0000-0000-000000000001",
        }

    def fake_search_arxiv(state):
        return {"arxiv_results": [], "tool_errors": [{"tool": "arxiv", "error": "failed"}]}

    def fake_search_web(state):
        return {"web_results": [], "tool_errors": [{"tool": "web", "error": "failed"}]}

    def fake_scrape_urls(state):
        return {"scraped_content": []}

    def fake_synthesize(state):
        return {"synthesis": "No sources", "key_findings": [], "sources": []}

    def fake_save_to_db(state):
        return {"session_id": state["session_id"]}

    monkeypatch.setattr(graph_module, "plan_searches", fake_plan_searches)
    monkeypatch.setattr(graph_module, "search_arxiv_node", fake_search_arxiv)
    monkeypatch.setattr(graph_module, "search_web_node", fake_search_web)
    monkeypatch.setattr(graph_module, "scrape_urls_node", fake_scrape_urls)
    monkeypatch.setattr(graph_module, "synthesize_node", fake_synthesize)
    monkeypatch.setattr(graph_module, "save_to_db_node", fake_save_to_db)

    graph = graph_module.build_graph()
    result = graph.invoke(
        {
            "question": "test",
            "search_queries": [],
            "core_entities": [],
            "arxiv_results": [],
            "web_results": [],
            "scraped_content": [],
            "synthesis": "",
            "key_findings": [],
            "sources": [],
            "tool_errors": [],
            "session_id": "",
            "duration_seconds": 0.0,
        }
    )

    assert result["tool_errors"] == [
        {"tool": "arxiv", "error": "failed"},
        {"tool": "web", "error": "failed"},
    ]
