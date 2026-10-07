"""initial: runs, events, audit_log, sop_versions, learning_store

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from backend.db.models import EVENT_AGENTS, EVENT_TYPES

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.run_id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("agent", sa.String(32), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.CheckConstraint(_in_list("type", EVENT_TYPES), name="ck_events_type"),
        sa.CheckConstraint(_in_list("agent", EVENT_AGENTS), name="ck_events_agent"),
    )
    op.create_index("ix_events_run_id", "events", ["run_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("run_id", sa.String(64)),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("params", JSONB(), nullable=False),
    )
    op.create_index("ix_audit_log_run_id", "audit_log", ["run_id"])
    op.execute(
        "CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'audit_log is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()"
    )
    op.create_table(
        "sop_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sop_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("sop_id", "version", name="uq_sop_versions_sop_version"),
    )
    op.create_index("ix_sop_versions_sop_id", "sop_versions", ["sop_id"])
    op.create_table(
        "learning_store",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64)),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_learning_store_run_id", "learning_store", ["run_id"])


def downgrade() -> None:
    op.drop_table("learning_store")
    op.drop_table("sop_versions")
    op.execute("DROP TRIGGER audit_log_no_change ON audit_log")
    op.drop_table("audit_log")
    op.execute("DROP FUNCTION audit_log_append_only()")
    op.drop_table("events")
    op.drop_table("runs")
