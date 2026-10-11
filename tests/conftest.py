"""Shared DB fixtures for tests that need Postgres (copied pattern from test_db.py)."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.db.config import get_database_url

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def shared_db_url():
    base = make_url(get_database_url())
    name = f"{base.database}_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"Cannot connect to Postgres: {e}", pytrace=False)
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield url
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(autouse=True)
def first_anomaly_by_default(monkeypatch):
    """R10b2/dev-03: runs skip anomalies that already have a lesson. Older tests repeat full runs on one
    database and expect the first anomaly each time, so they run with the skip off (also in subprocesses).
    tests/test_lessons_r10b2.py turns it back on (the product default)."""
    monkeypatch.setenv("SME_SKIP_HANDLED", "0")


@pytest.fixture
def db_session(shared_db_url):
    """One transaction per test, rolled back at the end."""
    engine = create_engine(shared_db_url)
    conn = engine.connect()
    trans = conn.begin()
    s = Session(conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()
    conn.close()
    engine.dispose()
