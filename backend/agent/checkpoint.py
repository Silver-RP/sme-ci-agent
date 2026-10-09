"""Postgres checkpointer (langgraph-checkpoint-postgres) built from DATABASE_URL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

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


# State types we put in checkpoints; allowed explicitly so LangGraph does not warn about unregistered types.
ALLOWED_MSGPACK_MODULES = [("backend.agent.state", "Hypothesis")]


def memory_checkpointer() -> InMemorySaver:
    """InMemorySaver that explicitly allows our own state types (no unregistered-type warning)."""
    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK_MODULES))
