from datetime import datetime

from pydantic import BaseModel


class ResearchRequest(BaseModel):
    question: str


class Source(BaseModel):
    title: str
    url: str
    source_type: str | None = None
    insight: str | None = None


class ToolError(BaseModel):
    tool: str
    query: str | None = None
    error: str


class ResearchResponse(BaseModel):
    session_id: str
    question: str
    summary: str
    key_findings: list[str]
    sources: list[Source]
    search_queries: list[str]
    core_entities: list[str]
    arxiv_count: int
    web_count: int
    duration_seconds: float
    tool_errors: list[ToolError]


class SessionSummary(BaseModel):
    session_id: str
    question: str
    sources: list[Source]
    search_queries: list[str]
    core_entities: list[str]
    arxiv_count: int
    web_count: int
    duration_seconds: float
    tool_errors: list[ToolError]
    created_at: datetime


class SessionDetail(SessionSummary):
    summary: str
    key_findings: list[str]
