import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_findings: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    search_queries: Mapped[list] = mapped_column(JSON, default=list)
    core_entities: Mapped[list] = mapped_column(JSON, default=list)
    tool_errors: Mapped[list] = mapped_column(JSON, default=list)
    arxiv_count: Mapped[int] = mapped_column(Integer, default=0)
    web_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
