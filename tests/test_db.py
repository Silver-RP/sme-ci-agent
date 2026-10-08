"""Test DB (T-013). Dùng DB riêng (tên ngẫu nhiên), tạo và xoá trong phiên test.

Không skip: thiếu Postgres thì fail với thông báo rõ ràng.
"""

import inspect
import json
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from backend.db import repo
from backend.db.config import DEFAULT_DATABASE_URL, get_database_url
from backend.db.models import EVENT_AGENTS, EVENT_TYPES

ROOT = Path(__file__).resolve().parent.parent
TABLES = {"runs", "events", "audit_log", "sop_versions", "learning_store"}


def _alembic_cfg(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session")
def test_db_url():
    base = make_url(get_database_url())
    name = f"{base.database}_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as e:  # noqa: BLE001
        pytest.fail(
            f"Không kết nối được Postgres ({base.render_as_string(hide_password=True)}). "
            f"Chạy `docker compose up -d db` trước. Lỗi: {e}",
            pytrace=False,
        )
    url = base.set(database=name).render_as_string(hide_password=False)
    yield url
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def migrated_url(test_db_url):
    command.upgrade(_alembic_cfg(test_db_url), "head")
    return test_db_url


@pytest.fixture
def session(migrated_url):
    """Mỗi test một transaction, rollback cuối test: không để lại dữ liệu."""
    engine = create_engine(migrated_url)
    conn = engine.connect()
    trans = conn.begin()
    s = Session(conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()
    conn.close()
    engine.dispose()


def _event(**over):
    e = {
        "event_id": "evt_0001",
        "run_id": "run_001",
        "ts": "2026-10-08T09:00:00Z",
        "type": "anomaly_detected",
        "agent": "quality",
        "domain": "manufacturing",
        "payload": {"kpi": "defect_rate", "value": 0.062, "machine": "M02"},
    }
    e.update(over)
    return e


def test_default_url_matches_env_example(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    example = (ROOT / ".env.example").read_text()
    assert f"DATABASE_URL={DEFAULT_DATABASE_URL}" in example
    assert get_database_url() == DEFAULT_DATABASE_URL
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@h/d")
    assert get_database_url() == "postgresql+psycopg://x:y@h/d"


def test_enums_match_contract():
    schema = json.loads((ROOT / "docs/schema/events.json").read_text())
    props = schema["properties"]
    assert tuple(props["type"]["enum"]) == EVENT_TYPES
    assert tuple(props["agent"]["enum"]) == EVENT_AGENTS


def test_migration_upgrade_downgrade_repeatable(test_db_url):
    cfg = _alembic_cfg(test_db_url)
    engine = create_engine(test_db_url)
    for _ in range(2):  # lặp lại: không rò trạng thái
        command.upgrade(cfg, "head")
        assert TABLES <= set(sa_inspect(engine).get_table_names())
        command.downgrade(cfg, "base")
        assert not (TABLES & set(sa_inspect(engine).get_table_names()))
    command.upgrade(cfg, "head")  # để các test khác dùng tiếp
    engine.dispose()


def test_event_roundtrip(session):
    repo.create_run(session, "run_001", "manufacturing")
    repo.record_event(session, _event())
    got = repo.get_event(session, "evt_0001")
    assert got["event_id"] == "evt_0001"
    assert got["run_id"] == "run_001"
    assert got["type"] == "anomaly_detected"
    assert got["agent"] == "quality"
    assert got["domain"] == "manufacturing"
    assert got["payload"] == _event()["payload"]
    assert got["ts"].startswith("2026-10-08T09:00:00")
    assert repo.get_event(session, "nope") is None


def test_event_rejects_bad_type_and_agent_and_shape(session):
    repo.create_run(session, "run_001", "manufacturing")
    with pytest.raises(ValueError):
        repo.record_event(session, _event(type="bogus"))
    with pytest.raises(ValueError):
        repo.record_event(session, _event(agent="bogus"))
    with pytest.raises(ValueError):
        repo.record_event(session, {k: v for k, v in _event().items() if k != "domain"})
    with pytest.raises(ValueError):
        repo.record_event(session, _event(extra=1))
    with pytest.raises(TypeError):
        repo.record_event(session, _event(payload="not-an-object"))
    assert repo.get_event(session, "evt_0001") is None


def test_db_constraint_rejects_bad_enum_even_bypassing_repo(session):
    repo.create_run(session, "run_001", "manufacturing")
    for bad_type, bad_agent in (("bogus", "quality"), ("anomaly_detected", "bogus")):
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO events (event_id, run_id, ts, type, agent, domain, payload) "
                    "VALUES ('e', 'run_001', now(), :t, :a, 'd', '{}')"
                ),
                {"t": bad_type, "a": bad_agent},
            )


def test_sop_versions_increment_without_overwrite(session):
    v1 = repo.add_sop_version(session, "SOP-1", "v1 text")
    v2 = repo.add_sop_version(session, "SOP-1", "v2 text")
    other = repo.add_sop_version(session, "SOP-2", "other")
    assert (v1.version, v2.version, other.version) == (1, 2, 1)
    assert repo.get_sop_version(session, "SOP-1", 1).content == "v1 text"
    assert repo.get_sop_version(session, "SOP-1").content == "v2 text"
    assert repo.get_sop_version(session, "SOP-9") is None
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            text(
                "INSERT INTO sop_versions (sop_id, version, content, created_by) "
                "VALUES ('SOP-1', 1, 'dup', 'x')"
            )
        )


def test_audit_log_append_only_api_and_db(session):
    funcs = {n for n, _ in inspect.getmembers(repo, inspect.isfunction)}
    assert "append_audit" in funcs
    assert [n for n in funcs if "audit" in n] == ["append_audit"]
    row = repo.append_audit(session, "agent", "query_logs", {"kpi": "defect_rate"})
    assert row.id is not None and row.params == {"kpi": "defect_rate"}
    for sql in ("UPDATE audit_log SET actor='x'", "DELETE FROM audit_log"):
        with pytest.raises(DBAPIError), session.begin_nested():
            session.execute(text(sql))


def test_learning_store_write(session):
    row = repo.save_learning(session, "manufacturing", {"lesson": "x"})
    assert row.id is not None


def test_no_leftover_data_between_tests(migrated_url):
    engine = create_engine(migrated_url)
    with engine.connect() as c:
        for table in TABLES:
            assert c.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table
    engine.dispose()


def test_alembic_cli_finds_backend_package(shared_db_url):
    """`uv run alembic upgrade head` (used by scripts/demo.sh) must import `backend` from the repo root."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    alembic_bin = Path(sys.executable).parent / "alembic"  # console script: does not put cwd on sys.path
    env = {**os.environ, "DATABASE_URL": shared_db_url, "PYTHONPATH": ""}
    proc = subprocess.run(
        [str(alembic_bin), "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr[-800:]
