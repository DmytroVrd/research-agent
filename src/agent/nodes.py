import json
import logging
import re
import time
import uuid
from difflib import SequenceMatcher

from agent.db.models import ResearchSession
from agent.db.session import SessionLocal
from agent.llm.openrouter import chat_completion
from agent.state import ResearchState
from agent.tools.arxiv import search as search_arxiv
from agent.tools.scraper import scrape
from agent.tools.web import search as search_web

logger = logging.getLogger(__name__)

ACADEMIC_HINTS = {
    "academic",
    "advance",
    "advances",
    "algorithm",
    "architecture",
    "arxiv",
    "benchmark",
    "deep learning",
    "evaluation",
    "experiment",
    "llm",
    "machine learning",
    "method",
    "model",
    "paper",
    "rag",
    "research",
    "retrieval augmented",
    "study",
    "survey",
    "technical",
}
STOPWORDS = {
    "about",
    "academic",
    "advance",
    "advances",
    "and",
    "are",
    "best",
    "biography",
    "current",
    "explain",
    "for",
    "from",
    "how",
    "into",
    "introduction",
    "is",
    "latest",
    "overview",
    "research",
    "source",
    "sources",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
}


def _source(title: str, url: str, source_type: str, insight: str = "") -> dict:
    return {
        "title": title.strip() or url,
        "url": url,
        "source_type": source_type,
        "insight": insight.strip(),
    }


def _candidate_sources(state: ResearchState) -> list[dict]:
    arxiv_sources = [
        _source(
            title=result.get("title", ""),
            url=result.get("url", ""),
            source_type="arxiv",
            insight=result.get("summary", "")[:220],
        )
        for result in state.get("arxiv_results", [])[:5]
        if result.get("url")
    ]
    web_sources = [
        _source(
            title=result.get("title", ""),
            url=result.get("url", ""),
            source_type="web",
            insight=result.get("snippet", "")[:220],
        )
        for result in state.get("web_results", [])[:5]
        if result.get("url")
    ]
    return arxiv_sources + web_sources


def _extract_json_object(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_string_array_field(text: str, field: str) -> list[str]:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def _extract_bool_field(text: str, field: str) -> bool | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*(true|false)', text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).lower() == "true"


def _parse_synthesis_response(text: str, fallback_sources: list[dict]) -> dict:
    parsed = _extract_json_object(text)
    summary = parsed.get("summary") if isinstance(parsed.get("summary"), str) else text.strip()
    key_findings = parsed.get("key_findings")
    cited_sources = parsed.get("cited_sources")

    if not isinstance(key_findings, list):
        key_findings = []
    key_findings = [finding.strip() for finding in key_findings if isinstance(finding, str)]

    if not isinstance(cited_sources, list):
        cited_sources = fallback_sources[:6]
    normalized_sources = []
    fallback_by_url = {source["url"]: source for source in fallback_sources}
    for source in cited_sources:
        if not isinstance(source, dict) or not source.get("url"):
            continue
        fallback = fallback_by_url.get(source["url"], {})
        normalized_sources.append(
            _source(
                title=str(source.get("title") or fallback.get("title") or source["url"]),
                url=str(source["url"]),
                source_type=str(source.get("source_type") or fallback.get("source_type") or ""),
                insight=str(source.get("insight") or fallback.get("insight") or ""),
            )
        )

    return {
        "summary": summary,
        "key_findings": key_findings[:5],
        "sources": normalized_sources[:6] or fallback_sources[:6],
    }


def _important_terms(question: str, queries: list[str]) -> list[str]:
    text = " ".join([question, *queries]).lower()
    terms = re.findall(r"[a-z0-9][a-z0-9.+#-]{1,}", text)
    deduped = []
    seen = set()
    for term in terms:
        term = term.strip("-")
        if len(term) < 3 or term in STOPWORDS or term in seen:
            continue
        deduped.append(term)
        seen.add(term)
    return deduped[:8]


def _is_relevant_result(result: dict, terms: list[str], text_keys: tuple[str, ...]) -> bool:
    if not terms:
        return True

    haystack = " ".join(str(result.get(key, "")) for key in text_keys).lower()
    haystack_words = set(re.findall(r"[a-z0-9][a-z0-9.+#-]{1,}", haystack))
    matches = [
        term
        for term in terms
        if term in haystack
        or any(SequenceMatcher(None, term, word).ratio() >= 0.82 for word in haystack_words)
    ]

    if len(terms) <= 2:
        return len(matches) == len(terms)
    return len(matches) >= min(2, len(terms))


def _filter_relevant_results(
    results: list[dict],
    *,
    question: str,
    queries: list[str],
    text_keys: tuple[str, ...],
) -> list[dict]:
    terms = _important_terms(question, queries)
    deduped = []
    seen_urls = set()
    for result in results:
        url = result.get("url")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped.append(result)

    filtered = []
    for result in deduped:
        if _is_relevant_result(result, terms=terms, text_keys=text_keys):
            filtered.append(result)
    return filtered


def _dedupe_queries(queries: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for query in queries:
        query = re.sub(r"(?<=[a-z])(?=(Who|What|When|Where|Why|How)\b)", "\n", query)
        for part in query.splitlines():
            part = re.sub(r"\s+", " ", part).strip(" -*0123456789.\t\"',")
            if part in {"{", "}", "[", "]"}:
                continue
            if re.fullmatch(r"(queries|core_entities|use_arxiv)\s*:?", part, flags=re.IGNORECASE):
                continue
            if not part:
                continue
            normalized = part.lower()
            if normalized in seen:
                continue
            cleaned.append(part)
            seen.add(normalized)
    return cleaned[:3]


def _fallback_queries(question: str) -> list[str]:
    question = question.strip()
    return _dedupe_queries([question, f"{question} overview", f"{question} official sources"])


def _fallback_core_entities(question: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3}\b", question)
    return _dedupe_queries([match for match in matches if match.lower() not in STOPWORDS])


def _looks_academic_question(question: str) -> bool:
    normalized = question.lower()
    return any(hint in normalized for hint in ACADEMIC_HINTS)


def _parse_search_plan(text: str, question: str) -> dict:
    parsed = _extract_json_object(text)
    queries = parsed.get("queries")
    if isinstance(queries, list):
        search_queries = _dedupe_queries([query for query in queries if isinstance(query, str)])
    else:
        search_queries = _dedupe_queries(_extract_string_array_field(text, "queries"))
        if not search_queries:
            search_queries = _dedupe_queries(text.splitlines())

    entities = parsed.get("core_entities")
    if isinstance(entities, list):
        core_entities = _dedupe_queries([entity for entity in entities if isinstance(entity, str)])
    else:
        core_entities = _dedupe_queries(_extract_string_array_field(text, "core_entities"))
        if not core_entities:
            core_entities = _fallback_core_entities(question)

    use_arxiv = parsed.get("use_arxiv")
    if not isinstance(use_arxiv, bool):
        use_arxiv = _extract_bool_field(text, "use_arxiv")
    if not isinstance(use_arxiv, bool):
        use_arxiv = _looks_academic_question(question)

    return {
        "search_queries": search_queries or _fallback_queries(question),
        "core_entities": core_entities,
        "use_arxiv": use_arxiv,
    }


def plan_searches(state: ResearchState) -> ResearchState:
    """Ask OpenRouter to generate 2-3 focused search queries for the question."""
    text = chat_completion(
        [
            {
                "role": "user",
                "content": (
                    f"Research question: {state['question']}\n\n"
                    "Return only valid JSON with this shape:\n"
                    "{\n"
                    '  "queries": ["query 1", "query 2", "query 3"],\n'
                    '  "core_entities": ["main named entity or product, if any"],\n'
                    '  "use_arxiv": true\n'
                    "}\n"
                    "core_entities should contain stable entity names or product names, "
                    "not long search phrases. Examples: Sam Altman, Hermes Agent, OpenAI. "
                    "Set use_arxiv=false for biographies, people, companies, products, "
                    "launch dates, or general web facts. Set use_arxiv=true only when the "
                    "question needs academic papers, scientific research, benchmarks, "
                    "technical methods, or surveys."
                ),
            }
        ],
        max_tokens=256,
        temperature=0.1,
    )
    plan = _parse_search_plan(text, state["question"])
    return {**plan, "session_id": str(uuid.uuid4())}


def search_arxiv_node(state: ResearchState) -> ResearchState:
    if not state.get("use_arxiv", True):
        return {"arxiv_results": []}

    results = []
    errors = []
    for query in state.get("search_queries", []):
        try:
            results.extend(search_arxiv(query, max_results=3))
        except RuntimeError as exc:
            logger.warning("arXiv search failed for query %r: %s", query, exc)
            errors.append({"tool": "arxiv", "query": query, "error": str(exc)})
    return {
        "arxiv_results": _filter_relevant_results(
            results,
            question=state["question"],
            queries=state.get("search_queries", []),
            text_keys=("title", "summary", "url"),
        ),
        "tool_errors": errors,
    }


def search_web_node(state: ResearchState) -> ResearchState:
    results = []
    errors = []
    queries = _dedupe_queries([*state.get("core_entities", []), *state.get("search_queries", [])])
    for query in queries:
        try:
            results.extend(search_web(query, max_results=3))
        except RuntimeError as exc:
            logger.warning("web search failed for query %r: %s", query, exc)
            errors.append({"tool": "web", "query": query, "error": str(exc)})
    return {
        "web_results": _filter_relevant_results(
            results,
            question=state["question"],
            queries=[*state.get("core_entities", []), *state.get("search_queries", [])],
            text_keys=("title", "snippet", "url"),
        ),
        "tool_errors": errors,
    }


def scrape_urls_node(state: ResearchState) -> ResearchState:
    top_urls = [result["url"] for result in state.get("web_results", [])[:3] if result.get("url")]
    scraped = [scrape(url) for url in top_urls]
    return {"scraped_content": scraped}


def synthesize_node(state: ResearchState) -> ResearchState:
    candidate_sources = _candidate_sources(state)
    if not candidate_sources:
        return {
            "synthesis": (
                "No relevant sources were found for this question. "
                "The agent did not generate an answer from model memory because this project "
                "requires source-grounded research outputs."
            ),
            "key_findings": [],
            "sources": [],
        }

    arxiv_text = "\n".join(
        f"[arXiv] {result['title']} ({result['url']}): {result['summary']}"
        for result in state.get("arxiv_results", [])[:5]
    )
    web_text = "\n".join(
        f"[Web] {result['title']} ({result['url']}): {result['snippet']}"
        for result in state.get("web_results", [])[:5]
    )
    scraped_text = "\n".join(
        f"[Scraped {result['url']}]:\n{result['content'][:500]}"
        for result in state.get("scraped_content", [])
        if result.get("content")
    )

    text = chat_completion(
        [
            {
                "role": "user",
                "content": (
                    f"Research question: {state['question']}\n\n"
                    f"Sources:\n{arxiv_text}\n{web_text}\n{scraped_text}\n\n"
                    "Return only valid JSON with this shape:\n"
                    "{\n"
                    '  "key_findings": ["finding 1", "finding 2", "finding 3"],\n'
                    '  "summary": "A concise 180-250 word synthesis.",\n'
                    '  "cited_sources": [\n'
                    '    {"title": "Source title", "url": "https://...", '
                    '"source_type": "arxiv|web", "insight": "one-line insight"}\n'
                    "  ]\n"
                    "}\n"
                    "Only cite URLs that appear in the provided sources. "
                    "If the evidence does not answer the question directly, say so clearly."
                ),
            }
        ],
        max_tokens=1024,
        temperature=0.2,
        session_id=state.get("session_id"),
    )
    parsed = _parse_synthesis_response(text, candidate_sources)
    return {
        "synthesis": parsed["summary"],
        "key_findings": parsed["key_findings"],
        "sources": parsed["sources"],
    }


def save_to_db_node(state: ResearchState) -> ResearchState:
    session_uuid = uuid.UUID(state["session_id"]) if state.get("session_id") else uuid.uuid4()
    started_at = state.get("started_at")
    duration_seconds = (
        time.perf_counter() - started_at if started_at else state.get("duration_seconds", 0.0)
    )
    with SessionLocal() as session:
        record = ResearchSession(
            id=session_uuid,
            question=state["question"],
            summary=state.get("synthesis", ""),
            key_findings=state.get("key_findings", []),
            sources=state.get("sources", []),
            search_queries=state.get("search_queries", []),
            core_entities=state.get("core_entities", []),
            tool_errors=state.get("tool_errors", []),
            arxiv_count=len(state.get("arxiv_results", [])),
            web_count=len(state.get("web_results", [])),
            duration_seconds=duration_seconds,
        )
        session.add(record)
        session.commit()
    return {"session_id": str(session_uuid), "duration_seconds": duration_seconds}
