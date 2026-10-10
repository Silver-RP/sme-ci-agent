"""API ghi/đọc. audit_log chỉ có append_audit (không có hàm sửa/xoá)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import (
    EVENT_AGENTS,
    EVENT_TYPES,
    AuditLog,
    Event,
    LearningEntry,
    Run,
    SopVersion,
)

EVENT_FIELDS = ("event_id", "run_id", "ts", "type", "agent", "domain", "payload")


def _parse_ts(ts: str | datetime) -> datetime:
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts)


def create_run(session: Session, run_id: str, domain: str) -> Run:
    run = Run(run_id=run_id, domain=domain)
    session.add(run)
    session.flush()
    return run


def record_event(session: Session, event: dict) -> Event:
    """Kiểm tra theo events.json trước khi ghi; sai thì ValueError."""
    missing = [f for f in EVENT_FIELDS if f not in event]
    if missing:
        raise ValueError(f"event thiếu trường: {missing}")
    extra = set(event) - set(EVENT_FIELDS)
    if extra:
        raise ValueError(f"event có trường lạ: {sorted(extra)}")
    if event["type"] not in EVENT_TYPES:
        raise ValueError(f"type không hợp lệ: {event['type']!r}")
    if event["agent"] not in EVENT_AGENTS:
        raise ValueError(f"agent không hợp lệ: {event['agent']!r}")
    if not isinstance(event["payload"], dict):
        raise TypeError("payload phải là object")
    row = Event(**{**event, "ts": _parse_ts(event["ts"])})
    session.add(row)
    session.flush()
    return row


def get_event(session: Session, event_id: str) -> dict | None:
    row = session.get(Event, event_id)
    if row is None:
        return None
    return {
        "event_id": row.event_id,
        "run_id": row.run_id,
        "ts": row.ts.isoformat(),
        "type": row.type,
        "agent": row.agent,
        "domain": row.domain,
        "payload": row.payload,
    }


def add_sop_version(
    session: Session,
    sop_id: str,
    content: str,
    created_by: str = "system",
    run_id: str | None = None,
) -> SopVersion:
    """Thêm bản mới = bản lớn nhất + 1 (bản đầu là 1); không ghi đè bản cũ."""
    current = session.scalar(select(func.max(SopVersion.version)).where(SopVersion.sop_id == sop_id))
    row = SopVersion(
        sop_id=sop_id,
        version=(current or 0) + 1,
        content=content,
        created_by=created_by,
        run_id=run_id,
    )
    session.add(row)
    session.flush()
    return row


def get_sop_version(session: Session, sop_id: str, version: int | None = None):
    q = select(SopVersion).where(SopVersion.sop_id == sop_id)
    if version is not None:
        q = q.where(SopVersion.version == version)
    else:
        q = q.order_by(SopVersion.version.desc())
    return session.scalars(q.limit(1)).first()


def append_audit(
    session: Session,
    actor: str,
    action: str,
    params: dict | None = None,
    run_id: str | None = None,
) -> AuditLog:
    row = AuditLog(actor=actor, action=action, params=params or {}, run_id=run_id)
    session.add(row)
    session.flush()
    return row


def save_learning(
    session: Session, domain: str, content: dict, run_id: str | None = None
) -> LearningEntry:
    row = LearningEntry(domain=domain, content=content, run_id=run_id)
    session.add(row)
    session.flush()
    return row


def list_learning(session: Session, domain: str) -> list[LearningEntry]:
    """Read only: lessons of one domain, newest first."""
    return list(
        session.scalars(select(LearningEntry).where(LearningEntry.domain == domain).order_by(LearningEntry.id.desc()))
    )


def recent_actions(session: Session, run_id: str | None = None, limit: int = 100) -> list[AuditLog]:
    """Read only: newest first, optionally one run."""
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if run_id is not None:
        q = q.where(AuditLog.run_id == run_id)
    return list(session.scalars(q))


def list_sop_versions(session: Session, sop_id: str) -> list[SopVersion]:
    """Read only: every stored version of one SOP, oldest first."""
    return list(session.scalars(select(SopVersion).where(SopVersion.sop_id == sop_id).order_by(SopVersion.version)))
