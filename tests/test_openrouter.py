from types import SimpleNamespace

import pytest

from agent.llm import openrouter


def test_chat_completion_posts_openrouter_request(monkeypatch):
    captured = {}

    class FakeResponse:
        text = '{"choices":[{"message":{"content":"hello"}}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "hello"}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(
        openrouter,
        "get_settings",
        lambda: SimpleNamespace(
            openrouter_api_key="test-key",
            openrouter_model="openrouter/free",
            openrouter_base_url="https://openrouter.ai/api/v1",
            openrouter_app_url="https://example.com",
            openrouter_app_title="AI Research Agent",
        ),
    )
    monkeypatch.setattr(openrouter.httpx, "Client", FakeClient)

    result = openrouter.chat_completion(
        [{"role": "user", "content": "Hi"}],
        max_tokens=32,
        session_id="session-1",
    )

    assert result == "hello"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["HTTP-Referer"] == "https://example.com"
    assert captured["json"]["model"] == "openrouter/free"
    assert captured["json"]["session_id"] == "session-1"


def test_chat_completion_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        openrouter,
        "get_settings",
        lambda: SimpleNamespace(
            openrouter_api_key="",
            openrouter_model="openrouter/free",
            openrouter_base_url="https://openrouter.ai/api/v1",
            openrouter_app_url="",
            openrouter_app_title="AI Research Agent",
        ),
    )

    with pytest.raises(openrouter.OpenRouterError, match="OPENROUTER_API_KEY"):
        openrouter.chat_completion([{"role": "user", "content": "Hi"}], max_tokens=32)


def test_chat_completion_accepts_structured_content(monkeypatch):
    class FakeResponse:
        text = '{"choices":[{"message":{"content":[{"type":"text","text":"hello"}]}}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": [{"type": "text", "text": "hello"}]}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, headers, json):
            return FakeResponse()

    monkeypatch.setattr(
        openrouter,
        "get_settings",
        lambda: SimpleNamespace(
            openrouter_api_key="test-key",
            openrouter_model="openrouter/free",
            openrouter_base_url="https://openrouter.ai/api/v1",
            openrouter_app_url="",
            openrouter_app_title="AI Research Agent",
        ),
    )
    monkeypatch.setattr(openrouter.httpx, "Client", FakeClient)

    assert openrouter.chat_completion([{"role": "user", "content": "Hi"}], max_tokens=32) == "hello"
