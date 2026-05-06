from types import SimpleNamespace

from agent.tools import web


def test_tavily_search_returns_results(monkeypatch):
    class FakeTavilyClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def search(
            self,
            query,
            search_depth,
            max_results,
            include_answer,
            include_raw_content,
        ):
            return {
                "results": [
                    {
                        "title": "Sam Altman - Wikipedia",
                        "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                        "content": "Samuel Harris Altman is an American entrepreneur.",
                    }
                ]
            }

    monkeypatch.setattr(web, "get_settings", lambda: SimpleNamespace(tavily_api_key="test-key"))
    monkeypatch.setattr(web, "TavilyClient", FakeTavilyClient)

    results = web._search_tavily("Sam Altman", max_results=3)

    assert results == [
        {
            "title": "Sam Altman - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/Sam_Altman",
            "snippet": "Samuel Harris Altman is an American entrepreneur.",
        }
    ]


def test_tavily_search_is_disabled_without_key(monkeypatch):
    monkeypatch.setattr(web, "get_settings", lambda: SimpleNamespace(tavily_api_key=""))

    assert web._search_tavily("Sam Altman", max_results=3) == []


def test_searchapi_duckduckgo_returns_knowledge_graph_and_organic_results(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "knowledge_graph": {
                    "title": "Sam Altman",
                    "description": "American entrepreneur and investor.",
                    "text": {"link": "https://en.wikipedia.org/wiki/Sam_Altman"},
                },
                "organic_results": [
                    {
                        "title": "Sam Altman - OpenAI",
                        "link": "https://openai.com/index/sam-altman/",
                        "snippet": "Sam Altman is associated with OpenAI.",
                    }
                ],
            }

    def fake_get(url, params, timeout, follow_redirects):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr(web, "get_settings", lambda: SimpleNamespace(searchapi_api_key="test-key"))
    monkeypatch.setattr(web.httpx, "get", fake_get)

    results = web._search_searchapi_duckduckgo("Sam Altman", max_results=5)

    assert captured["url"] == web.SEARCHAPI_URL
    assert captured["params"]["engine"] == "duckduckgo"
    assert captured["params"]["q"] == "Sam Altman"
    assert results == [
        {
            "title": "Sam Altman",
            "url": "https://en.wikipedia.org/wiki/Sam_Altman",
            "snippet": "American entrepreneur and investor.",
        },
        {
            "title": "Sam Altman - OpenAI",
            "url": "https://openai.com/index/sam-altman/",
            "snippet": "Sam Altman is associated with OpenAI.",
        },
    ]


def test_searchapi_duckduckgo_is_disabled_without_key(monkeypatch):
    monkeypatch.setattr(web, "get_settings", lambda: SimpleNamespace(searchapi_api_key=""))

    assert web._search_searchapi_duckduckgo("Sam Altman", max_results=3) == []


def test_search_prefers_tavily_then_supplements_with_fallbacks(monkeypatch):
    monkeypatch.setattr(
        web,
        "_search_tavily",
        lambda query, max_results: [
            {
                "title": "Sam Altman - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                "snippet": "American entrepreneur",
            }
        ],
    )
    monkeypatch.setattr(web, "_search_searchapi_duckduckgo", lambda query, max_results: [])
    monkeypatch.setattr(
        web,
        "_search_duckduckgo",
        lambda query, max_results: [
            {
                "title": "OpenAI - Sam Altman",
                "url": "https://openai.com/index/sam-altman/",
                "snippet": "Sam Altman at OpenAI.",
            }
        ],
    )
    monkeypatch.setattr(
        web,
        "_search_wikipedia",
        lambda query, max_results: [
            {
                "title": "Duplicate",
                "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                "snippet": "Duplicate URL",
            }
        ],
    )

    results = web.search("Who is Sam Altman?", max_results=5)

    assert [result["url"] for result in results] == [
        "https://en.wikipedia.org/wiki/Sam_Altman",
        "https://openai.com/index/sam-altman/",
    ]


def test_wikipedia_search_sends_user_agent(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                "Sam Altman",
                ["Sam Altman"],
                ["American entrepreneur"],
                ["https://en.wikipedia.org/wiki/Sam_Altman"],
            ]

    def fake_get(url, headers, params, timeout, follow_redirects):
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(web.httpx, "get", fake_get)

    results = web._search_wikipedia("Sam Altman", 3)

    assert "User-Agent" in captured["headers"]
    assert results[0]["title"] == "Sam Altman"


def test_search_falls_back_to_wikipedia(monkeypatch):
    monkeypatch.setattr(web, "_search_searchapi_duckduckgo", lambda query, max_results: [])
    monkeypatch.setattr(web, "_search_duckduckgo", lambda query, max_results: [])
    monkeypatch.setattr(
        web,
        "_search_wikipedia",
        lambda query, max_results: [
            {
                "title": "Sam Altman",
                "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                "snippet": "American entrepreneur",
            }
        ],
    )

    results = web.search("Sam Altman", max_results=3)

    assert results == [
        {
            "title": "Sam Altman",
            "url": "https://en.wikipedia.org/wiki/Sam_Altman",
            "snippet": "American entrepreneur",
        }
    ]


def test_search_tries_simplified_wikipedia_query(monkeypatch):
    calls = []

    monkeypatch.setattr(web, "_search_searchapi_duckduckgo", lambda query, max_results: [])
    monkeypatch.setattr(web, "_search_duckduckgo", lambda query, max_results: [])

    def fake_wikipedia(query, max_results):
        calls.append(query)
        if query == "Sam Altman":
            return [
                {
                    "title": "Sam Altman",
                    "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                    "snippet": "American entrepreneur",
                }
            ]
        return []

    monkeypatch.setattr(web, "_search_wikipedia", fake_wikipedia)

    results = web.search("Sam Altman biography", max_results=3)

    assert calls == ["Sam Altman biography", "Sam Altman"]
    assert results[0]["title"] == "Sam Altman"


def test_search_simplifies_possessive_wikipedia_query(monkeypatch):
    calls = []

    monkeypatch.setattr(web, "_search_searchapi_duckduckgo", lambda query, max_results: [])
    monkeypatch.setattr(web, "_search_duckduckgo", lambda query, max_results: [])

    def fake_wikipedia(query, max_results):
        calls.append(query)
        if query == "Sam Altman":
            return [
                {
                    "title": "Sam Altman",
                    "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                    "snippet": "American entrepreneur",
                }
            ]
        return []

    monkeypatch.setattr(web, "_search_wikipedia", fake_wikipedia)

    results = web.search("Sam Altman's biography", max_results=3)

    assert "Sam Altman" in calls
    assert results[0]["url"] == "https://en.wikipedia.org/wiki/Sam_Altman"


def test_search_supplements_duckduckgo_with_wikipedia(monkeypatch):
    monkeypatch.setattr(web, "_search_searchapi_duckduckgo", lambda query, max_results: [])
    monkeypatch.setattr(
        web,
        "_search_duckduckgo",
        lambda query, max_results: [
            {
                "title": "Unrelated result",
                "url": "https://example.com/unrelated",
                "snippet": "Not enough context",
            }
        ],
    )
    monkeypatch.setattr(
        web,
        "_search_wikipedia",
        lambda query, max_results: [
            {
                "title": "Sam Altman",
                "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                "snippet": "American entrepreneur",
            }
        ],
    )

    results = web.search("Sam Altman biography", max_results=3)

    assert len(results) == 2
    assert results[1]["title"] == "Sam Altman"


def test_search_returns_empty_when_all_providers_fail(monkeypatch):
    def raise_runtime_error(query, max_results):
        raise RuntimeError("failed")

    monkeypatch.setattr(web, "_search_duckduckgo", raise_runtime_error)
    monkeypatch.setattr(web, "_search_searchapi_duckduckgo", raise_runtime_error)
    monkeypatch.setattr(web, "_search_wikipedia", raise_runtime_error)

    assert web.search("anything") == []
