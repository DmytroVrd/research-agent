from operator import add
from typing import Annotated, TypedDict


class ResearchState(TypedDict, total=False):
    question: str
    search_queries: list[str]
    core_entities: list[str]
    use_arxiv: bool
    arxiv_results: list[dict]
    web_results: list[dict]
    scraped_content: list[dict]
    synthesis: str
    key_findings: list[str]
    sources: list[dict]
    tool_errors: Annotated[list[dict], add]
    session_id: str
    duration_seconds: float
    started_at: float
