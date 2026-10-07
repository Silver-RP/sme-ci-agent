"""Postgres checkpointer (langgraph-checkpoint-postgres) built from DATABASE_URL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver

from backend.db.config import get_database_url


def _psycopg_url(url: str) -> str:
    """SQLAlchemy URL (postgresql+psycopg://) -> plain libpq URL for psycopg."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def postgres_checkpointer(url: str | None = None) -> Iterator[PostgresSaver]:
    """Yield a ready PostgresSaver (tables created if missing); connection closes on exit."""
    with PostgresSaver.from_conn_string(_psycopg_url(url or get_database_url())) as saver:
        saver.setup()
        yield saver
