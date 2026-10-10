"""R10c/dev-01 (H-37): one shared SQLAlchemy engine, sessions closed when a run ends, engine disposed on shutdown."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.api.app import create_app
from backend.db.config import max_connections
from backend.db.session import dispose_shared_engines, get_shared_engine
from backend.domain_config import load_domain_config

CFG = load_domain_config()
ROOT = Path(__file__).resolve().parent.parent
ANSWER = {"answer": "I have no further information about this."}


@pytest.fixture
def own_db_url(shared_db_url):
    """A private migrated database: the default app commits for real, which must not leak into other tests."""
    base = make_url(shared_db_url)
    name = f"{base.database}_pool"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield url
    dispose_shared_engines()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def default_app(own_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", own_db_url)
    monkeypatch.setenv("SME_LLM", "scripted")
    with TestClient(create_app(CFG)) as client:
        yield client


def _start(c):
    r = c.post("/runs", json={})
    assert r.status_code == 201, r.text
    return r.json()


def test_two_runs_share_one_engine(default_app):
    a, b = _start(default_app), _start(default_app)
    runs = default_app.app.state.runs
    ea = runs[a["run_id"]].ctx.session.get_bind()
    eb = runs[b["run_id"]].ctx.session.get_bind()
    assert ea is eb
    assert ea is get_shared_engine()


def test_get_shared_engine_is_cached_per_url(shared_db_url):
    assert get_shared_engine(shared_db_url) is get_shared_engine(shared_db_url)


def test_100_runs_do_not_exceed_pool(default_app, own_db_url):
    for _ in range(100):
        run = _start(default_app)
        if run["pending"] and run["pending"]["type"] == "answer":  # go on to the steps that use the DB
            r = default_app.post(f"/runs/{run['run_id']}/answer", json=ANSWER)
            assert r.status_code == 200, r.text
    url = make_url(own_db_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            n = c.execute(
                text("select count(*) from pg_stat_activity where datname = :d"), {"d": url.database}
            ).scalar_one()
    finally:
        admin.dispose()
    assert n <= max_connections(), f"{n} connections > pool limit {max_connections()}"


def test_session_closed_when_run_finishes(default_app):
    # drive a scripted run to the end: approve the proposal, then finish at whatever comes next
    run = _start(default_app)
    rid = run["run_id"]
    if run["pending"]["type"] == "answer":
        run = default_app.post(f"/runs/{rid}/answer", json=ANSWER).json()
    for _ in range(10):
        p = run["pending"]
        if p is None:
            break
        decision = "approved" if p["kind"] == "proposal" else "finish"
        run = default_app.post(
            f"/runs/{rid}/approval",
            json={"proposal_id": p["proposal_id"], "kind": p["kind"], "decision": decision, "decided_by": "alice"},
        ).json()
    assert run["state"] == "finished", run
    engine = get_shared_engine()
    assert engine.pool.checkedout() == 0


def test_shutdown_disposes_engine(own_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", own_db_url)
    monkeypatch.setenv("SME_LLM", "scripted")
    with TestClient(create_app(CFG)) as c:
        _start(c)
        assert c.get("/audit").status_code == 200  # opens (and returns) a pooled connection
        engine = get_shared_engine()
        assert engine.pool.checkedin() >= 1
    assert engine.pool.checkedin() == 0
