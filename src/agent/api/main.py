import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.api.schemas import ResearchRequest, ResearchResponse, SessionDetail, SessionSummary
from agent.db.models import Base, ResearchSession
from agent.db.session import engine, get_session
from agent.graph import research_graph
from agent.llm.openrouter import OpenRouterError


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI Research Agent", lifespan=lifespan)
SessionDep = Annotated[Session, Depends(get_session)]
STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


def _normalize_sources(raw_sources: list) -> list[dict]:
    normalized = []
    for source in raw_sources or []:
        if isinstance(source, str):
            normalized.append(
                {"title": source, "url": source, "source_type": None, "insight": None}
            )
            continue
        if not isinstance(source, dict) or not source.get("url"):
            continue
        url = str(source["url"])
        normalized.append(
            {
                "title": str(source.get("title") or url),
                "url": url,
                "source_type": source.get("source_type"),
                "insight": source.get("insight"),
            }
        )
    return normalized


def _research_response_from_state(result: dict) -> ResearchResponse:
    return ResearchResponse(
        session_id=result["session_id"],
        question=result["question"],
        summary=result["synthesis"],
        key_findings=result.get("key_findings", []),
        sources=_normalize_sources(result.get("sources", [])),
        search_queries=result.get("search_queries", []),
        core_entities=result.get("core_entities", []),
        arxiv_count=len(result.get("arxiv_results", [])),
        web_count=len(result.get("web_results", [])),
        duration_seconds=result.get("duration_seconds", 0.0),
        tool_errors=result.get("tool_errors", []),
    )


def _session_summary(record: ResearchSession) -> SessionSummary:
    return SessionSummary(
        session_id=str(record.id),
        question=record.question,
        sources=_normalize_sources(record.sources),
        search_queries=record.search_queries or [],
        core_entities=record.core_entities or [],
        arxiv_count=record.arxiv_count,
        web_count=record.web_count,
        duration_seconds=record.duration_seconds,
        tool_errors=record.tool_errors or [],
        created_at=record.created_at,
    )


def _session_detail(record: ResearchSession) -> SessionDetail:
    return SessionDetail(
        **_session_summary(record).model_dump(),
        summary=record.summary,
        key_findings=record.key_findings or [],
    )


@app.post("/research", response_model=ResearchResponse)
def run_research(request: ResearchRequest):
    initial_state = {
        "question": request.question,
        "search_queries": [],
        "core_entities": [],
        "use_arxiv": True,
        "arxiv_results": [],
        "web_results": [],
        "scraped_content": [],
        "synthesis": "",
        "key_findings": [],
        "sources": [],
        "tool_errors": [],
        "session_id": "",
        "duration_seconds": 0.0,
        "started_at": time.perf_counter(),
    }
    try:
        result = research_graph.invoke(initial_state)
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _research_response_from_state(result)


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions(session: SessionDep, limit: int = 20):
    limit = max(1, min(limit, 100))
    records = session.scalars(
        select(ResearchSession).order_by(ResearchSession.created_at.desc()).limit(limit)
    ).all()
    return [_session_summary(record) for record in records]


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def get_research_session(session_id: str, session: SessionDep):
    try:
        record_id = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc

    record = session.get(ResearchSession, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_detail(record)
