"""SQLAlchemy models: runs, events, audit_log, sop_versions, learning_store."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Khớp docs/schema/events.json (test so sánh với file hợp đồng).
EVENT_TYPES = (
    "anomaly_detected",
    "hypothesis_updated",
    "tool_called",
    "question_asked",
    "answer_received",
    "proposal_created",
    "approval_decided",
    "sop_applied",
    "kpi_measured",
    "rollback_done",
    "learning_saved",
    "run_finished",
)
EVENT_AGENTS = ("quality", "investigation", "improvement", "system")

JsonType = JSON().with_variant(JSONB(), "postgresql")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(_in_list("type", EVENT_TYPES), name="ck_events_type"),
        CheckConstraint(_in_list("agent", EVENT_AGENTS), name="ck_events_agent"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("runs.run_id"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    agent: Mapped[str] = mapped_column(String(32), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)


class AuditLog(Base):
    """Chỉ thêm. DB có trigger chặn sửa/xoá (xem migration)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    params: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)


class SopVersion(Base):
    __tablename__ = "sop_versions"
    __table_args__ = (UniqueConstraint("sop_id", "version", name="uq_sop_versions_sop_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sop_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    run_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningEntry(Base):
    __tablename__ = "learning_store"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
