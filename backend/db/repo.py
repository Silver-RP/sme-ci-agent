"""API ghi/đọc. audit_log chỉ có append_audit (không có hàm sửa/xoá)."""

import math
from datetime import date, datetime

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


def update_run(session: Session, run_id: str, status: str, finished_at: str | datetime | None) -> None:
    """Keep runs.status / finished_at in step with the run (H-15)."""
    row = session.get(Run, run_id)
    if row is None:
        raise ValueError(f"run {run_id!r} not found")
    row.status = status
    row.finished_at = _parse_ts(finished_at) if finished_at else None
    session.flush()


def list_runs(session: Session) -> list[Run]:
    """All runs, newest first."""
    return list(session.scalars(select(Run).order_by(Run.started_at.desc(), Run.run_id.desc())))


def list_run_events(session: Session, run_id: str) -> list[dict]:
    """Events of one run as dicts, oldest first."""
    rows = session.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.ts, Event.event_id))
    return [
        {
            "event_id": r.event_id, "run_id": r.run_id, "ts": r.ts.isoformat(), "type": r.type,
            "agent": r.agent, "domain": r.domain, "payload": r.payload,
        }
        for r in rows
    ]


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


def to_jsonable(v):
    """Equivalent JSON value: dict/list keep their structure (never ``str(dict)``), datetime -> ISO string,
    numpy scalars/arrays -> Python values, NaN/inf -> None. Anything else unknown falls back to ``str``."""
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {str(k): to_jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset)):
        return [to_jsonable(x) for x in v]
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "tolist"):  # numpy scalar or array
        return to_jsonable(v.tolist())
    if hasattr(v, "isoformat"):  # pandas Timestamp and similar
        return v.isoformat()
    return str(v)


def append_audit(
    session: Session,
    actor: str,
    action: str,
    params: dict | None = None,
    run_id: str | None = None,
) -> AuditLog:
    row = AuditLog(actor=actor, action=action, params=to_jsonable(params or {}), run_id=run_id)
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


def list_learning(session: Session, domain: str, limit: int | None = None) -> list[LearningEntry]:
    """Read only: lessons of one domain, newest first (at most `limit` when given)."""
    q = select(LearningEntry).where(LearningEntry.domain == domain).order_by(LearningEntry.id.desc())
    if limit is not None:
        q = q.limit(limit)
    return list(session.scalars(q))


def recent_actions(session: Session, run_id: str | None = None, limit: int = 100) -> list[AuditLog]:
    """Read only: newest first, optionally one run."""
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if run_id is not None:
        q = q.where(AuditLog.run_id == run_id)
    return list(session.scalars(q))


def list_sop_versions(session: Session, sop_id: str) -> list[SopVersion]:
    """Read only: every stored version of one SOP, oldest first."""
    return list(session.scalars(select(SopVersion).where(SopVersion.sop_id == sop_id).order_by(SopVersion.version)))
