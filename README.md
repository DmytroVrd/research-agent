# AI Research Agent

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-agent_graph-4B5563)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED)

Source-grounded AI research agent built with **LangGraph**, **OpenRouter**, **FastAPI**,
**PostgreSQL**, and **Docker**.

The agent takes a research question, plans focused search queries, retrieves evidence from
multiple sources, scrapes selected pages, synthesizes a structured answer, and persists every
research session for later review.

![AI Research Agent Web UI](docs/assets/research-agent-ui.png)

## Why This Project

This project is designed as a practical AI/Python portfolio project, not just a single LLM API
call. It demonstrates:

- agent workflow orchestration with LangGraph
- source-grounded answer generation
- web and academic retrieval
- PostgreSQL persistence
- FastAPI API design
- Dockerized local development
- test coverage for graph nodes, tools, API routes, and parsing edge cases
- a clean web UI for demoing the project without Swagger

## Features

- **Research planning**: generates focused search queries and core entities for each question.
- **Multi-source retrieval**: Tavily, optional SearchAPI DuckDuckGo, DuckDuckGo fallback,
  Wikipedia fallback, and arXiv for academic questions.
- **Question-aware arXiv routing**: skips arXiv for biographies, products, companies, and
  general web facts.
- **Source-grounded synthesis**: refuses to answer from model memory when no relevant sources
  are found.
- **Structured output**: summary, numbered key findings, sources with title/URL/insight,
  generated search queries, core entities, runtime, and tool errors.
- **Session history**: saves every research run in PostgreSQL and exposes it through API and UI.
- **Web UI**: one-page interface for running research, browsing history, and loading sessions
  by ID.

## Architecture

```text
question
  -> plan_searches
  -> search_arxiv       \
  -> search_web          -> scrape_urls -> synthesize -> save_to_db
  -> source filtering   /
```

Main components:

- **LangGraph**: stateful multi-step research workflow
- **OpenRouter**: free-model-compatible LLM gateway for planning and synthesis
- **Tavily**: primary search provider for stronger web retrieval
- **DuckDuckGo/Wikipedia**: fallback retrieval when paid/keyed providers are unavailable
- **arXiv**: academic paper search for research-heavy questions
- **FastAPI**: API and static web UI
- **PostgreSQL + SQLAlchemy + Alembic**: persistent research session storage

## Quick Start

Create a local environment file:

```bash
cp .env.example .env
```

Set at least:

```env
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-dev-...
DATABASE_URL=postgresql://postgres:postgres@db:5432/research_agent
```

Run the app and database:

```bash
docker compose up -d
```

Open the web UI:

```text
http://localhost:8000/
```

API docs:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

## Demo Questions

Good questions for a portfolio demo:

```text
What is Hermes Agent and who created this?
What is OpenClaw and who created this?
Who is Andrej Karpathy?
Who is Sam Altman?
What is RAG in AI?
What is LangGraph and when should you use it?
Compare vector databases for RAG: Pinecone, Weaviate, and Qdrant.
```

These examples exercise different behavior:

- people and company/product questions should use web sources, not arXiv noise
- technical/research questions should produce grounded implementation-oriented summaries
- the response should include citations and generated search queries
- empty-source cases should not produce hallucinated answers

## API

### `POST /research`

Request:

```json
{
  "question": "Who is Andrej Karpathy?"
}
```

Response shape:

```json
{
  "session_id": "uuid",
  "question": "Who is Andrej Karpathy?",
  "summary": "Structured source-grounded synthesis...",
  "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
  "sources": [
    {
      "title": "Source title",
      "url": "https://example.com",
      "source_type": "web",
      "insight": "Why this source matters"
    }
  ],
  "search_queries": ["generated query"],
  "core_entities": ["Andrej Karpathy"],
  "arxiv_count": 0,
  "web_count": 5,
  "duration_seconds": 12.4,
  "tool_errors": []
}
```

### `GET /sessions`

Returns the latest persisted research sessions from PostgreSQL.

```bash
curl http://localhost:8000/sessions?limit=10
```

### `GET /sessions/{session_id}`

Returns a full stored session, including summary, findings, sources, generated queries,
core entities, counts, tool errors, and runtime.

```bash
curl http://localhost:8000/sessions/<session-id>
```

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | OpenRouter API key used for planning and synthesis |
| `OPENROUTER_MODEL` | no | Defaults to `openrouter/free` |
| `OPENROUTER_BASE_URL` | no | Defaults to `https://openrouter.ai/api/v1` |
| `TAVILY_API_KEY` | recommended | Primary web search provider |
| `SEARCHAPI_API_KEY` | optional | Enables SearchAPI DuckDuckGo provider |
| `DATABASE_URL` | yes | PostgreSQL connection string |

## Local Development

```bash
pip install -e ".[dev]"
ruff check src tests
pytest
```

Run the API locally without Docker:

```bash
uvicorn agent.api.main:app --reload
```

For local PostgreSQL outside Docker, use:

```bash
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/research_agent
```

## Database Migrations

Apply migrations:

```bash
alembic upgrade head
```

Create a new migration:

```bash
alembic revision --autogenerate -m "describe change"
```

## Testing

The test suite covers:

- FastAPI endpoints
- session persistence endpoints
- LangGraph node behavior
- OpenRouter error handling
- search provider parsing and fallbacks
- malformed LLM JSON recovery
- no-source synthesis guard

Run:

```bash
ruff check src tests
pytest
```

## Evaluation Notes

The `evals/` folder contains demo questions and qualitative checks used to inspect answer
quality. These are intentionally lightweight because live research evals consume search and
LLM API credits.

Expected quality checks:

- sources are not empty for answerable questions
- source titles and URLs are returned, not bare links
- generated search queries are readable
- biography/product questions do not get irrelevant arXiv papers
- summary is grounded in retrieved sources
- failed tools are reported instead of crashing the request

## Project Structure

```text
src/agent/
  api/        FastAPI app, schemas, and static web UI
  db/         SQLAlchemy models and session factory
  llm/        OpenRouter client
  tools/      arXiv, web search, and scraper tools
  graph.py    LangGraph assembly
  nodes.py    Agent node implementations
  state.py    ResearchState definition
tests/        Unit and API tests
evals/        Demo questions and qualitative eval notes
alembic/      Database migrations
```

## Status

This is a local-first portfolio project. The app is ready to run with Docker and can be
published to GitHub with environment variables kept out of the repository.
