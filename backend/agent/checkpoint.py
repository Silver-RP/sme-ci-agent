"""Postgres checkpointer (langgraph-checkpoint-postgres) built from DATABASE_URL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import Connection
from psycopg.rows import dict_row

from backend.db.config import get_database_url


def _psycopg_url(url: str) -> str:
    """SQLAlchemy URL (postgresql+psycopg://) -> plain libpq URL for psycopg."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


# State types we put in checkpoints; allowed explicitly so LangGraph does not warn about unregistered types.
ALLOWED_MSGPACK_MODULES = [("backend.agent.state", "Hypothesis")]


@contextmanager
def postgres_checkpointer(url: str | None = None) -> Iterator[PostgresSaver]:
    """Yield a ready PostgresSaver (tables created if missing); connection closes on exit.

    The serializer allows our own state types, so a state with ``Hypothesis`` reads back as ``Hypothesis``."""
    serde = JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK_MODULES)
    with Connection.connect(
        _psycopg_url(url or get_database_url()), autocommit=True, prepare_threshold=0, row_factory=dict_row
    ) as conn:
        saver = PostgresSaver(conn, serde=serde)
        saver.setup()
        yield saver


def memory_checkpointer() -> InMemorySaver:
    """InMemorySaver that explicitly allows our own state types (no unregistered-type warning)."""
    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK_MODULES))
