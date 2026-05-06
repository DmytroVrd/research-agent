import re

import httpx
from duckduckgo_search import DDGS
from tavily import TavilyClient

from agent.config import get_settings

MAX_RESULTS = 5
SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "AIResearchAgent/0.1 (local portfolio project; contact: local-dev)"
QUERY_NOISE = (
    "biography",
    "career",
    "overview",
    "official sources",
    "official source",
    "profile",
    "who is",
    "what is",
)


def _search_tavily(query: str, max_results: int) -> list[dict]:
    settings = get_settings()
    if not settings.tavily_api_key:
        return []

    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
        )
    except Exception as exc:
        raise RuntimeError("Tavily search failed") from exc

    return [
        {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "snippet": result.get("content", ""),
        }
        for result in response.get("results", [])
        if result.get("url")
    ]


def _search_searchapi_duckduckgo(query: str, max_results: int) -> list[dict]:
    settings = get_settings()
    api_key = getattr(settings, "searchapi_api_key", "")
    if not api_key:
        return []

    try:
        response = httpx.get(
            SEARCHAPI_URL,
            params={
                "engine": "duckduckgo",
                "q": query,
                "api_key": api_key,
                "safe": "moderate",
            },
            timeout=15,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError("SearchAPI DuckDuckGo search failed") from exc

    results = []
    knowledge_graph = payload.get("knowledge_graph")
    if isinstance(knowledge_graph, dict):
        kg_link = knowledge_graph.get("website")
        text = knowledge_graph.get("text")
        if isinstance(text, dict):
            kg_link = text.get("link") or kg_link
        if kg_link:
            results.append(
                {
                    "title": knowledge_graph.get("title", ""),
                    "url": kg_link,
                    "snippet": knowledge_graph.get("description", ""),
                }
            )

    organic_results = payload.get("organic_results", [])
    if isinstance(organic_results, list):
        results.extend(
            {
                "title": result.get("title", ""),
                "url": result.get("link", ""),
                "snippet": result.get("snippet", ""),
            }
            for result in organic_results
            if isinstance(result, dict) and result.get("link")
        )

    return results[:max_results]


def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
    except Exception as exc:
        raise RuntimeError("DuckDuckGo search failed") from exc
    return [
        {
            "title": result.get("title", ""),
            "url": result.get("href", ""),
            "snippet": result.get("body", ""),
        }
        for result in results
    ]


def _search_wikipedia(query: str, max_results: int) -> list[dict]:
    try:
        response = httpx.get(
            WIKIPEDIA_API_URL,
            headers={"User-Agent": USER_AGENT},
            params={
                "action": "opensearch",
                "search": query,
                "limit": max_results,
                "namespace": 0,
                "format": "json",
            },
            timeout=10,
            follow_redirects=True,
        )
        response.raise_for_status()
        _, titles, descriptions, urls = response.json()
    except Exception as exc:
        raise RuntimeError("Wikipedia fallback search failed") from exc

    return [
        {"title": title, "url": url, "snippet": description}
        for title, description, url in zip(titles, descriptions, urls, strict=False)
        if url
    ]


def _query_variants(query: str) -> list[str]:
    variants = [query.strip()]
    simplified = query.strip(" ?")
    lowered = simplified.lower()
    lowered = re.sub(r"\b([a-z0-9]+)(?:'s|\u2019s)\b", r"\1", lowered)
    for noise in QUERY_NOISE:
        lowered = lowered.replace(noise, "")
    simplified = " ".join(lowered.split()).title()
    if simplified and simplified.lower() != query.strip().lower():
        variants.append(simplified)
    entity_like = re.sub(
        r"\b(and|at|background|career|company|current|influence|leadership|policy|professional|role|timeline)\b",
        "",
        simplified,
        flags=re.IGNORECASE,
    )
    entity_like = " ".join(entity_like.split())
    if entity_like and entity_like.lower() not in {variant.lower() for variant in variants}:
        variants.append(entity_like)
    return variants


def _append_unique(results: list[dict], candidates: list[dict], seen_urls: set[str]) -> None:
    for result in candidates:
        url = result.get("url")
        if url and url not in seen_urls:
            results.append(result)
            seen_urls.add(url)


def search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    results = []
    seen_urls: set[str] = set()

    try:
        _append_unique(results, _search_tavily(query, max_results=max_results), seen_urls)
    except RuntimeError:
        pass

    try:
        _append_unique(
            results,
            _search_searchapi_duckduckgo(query, max_results=max_results),
            seen_urls,
        )
    except RuntimeError:
        pass

    try:
        _append_unique(results, _search_duckduckgo(query, max_results=max_results), seen_urls)
    except RuntimeError:
        pass

    for variant in _query_variants(query):
        try:
            wiki_results = _search_wikipedia(variant, max_results=max_results)
        except RuntimeError:
            wiki_results = []
        _append_unique(results, wiki_results, seen_urls)
        if len(results) >= max_results:
            break

    return results[:max_results]
