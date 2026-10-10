"""`scripts/demo.sh --fresh-db` (leader duyệt 2026-10-10): demo chạy trên DB riêng `<db>_demo`, tạo lại sạch mỗi lần.

Chỉ xoá DB có hậu tố `_demo`; DB chính (`sme_ci`) không bị đụng. Cần Postgres như tests/test_db.py.
"""

import importlib.util
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.db.config import get_database_url

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fresh_db", ROOT / "scripts" / "fresh_db.py")
fresh_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh_db)


@pytest.fixture
def base_url():
    """Một DB "chính" tạm (tên ngẫu nhiên) để kiểm rằng nó không bị đụng; xoá cả nó và bản _demo sau test."""
    base = make_url(get_database_url())
    name = f"{base.database}_fdb_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    yield url
    with admin.connect() as c:
        for db in (name, f"{name}_demo"):
            c.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
    admin.dispose()


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as c:
        rows = c.execute(text("select tablename from pg_tables where schemaname = 'public'")).scalars().all()
    engine.dispose()
    return set(rows)


def _make_table(url: str, name: str) -> None:
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text(f"create table {name} (id int)"))
    engine.dispose()


def test_demo_url_only_changes_the_database_name():
    url = "postgresql+psycopg://sme:sme@localhost:5433/sme_ci"
    assert fresh_db.demo_url(url) == "postgresql+psycopg://sme:sme@localhost:5433/sme_ci_demo"
    assert fresh_db.demo_url(fresh_db.demo_url(url)).endswith("/sme_ci_demo")  # idempotent


def test_recreate_gives_an_empty_demo_db_and_leaves_the_main_db_alone(base_url):
    _make_table(base_url, "keep_me")
    demo = fresh_db.recreate(base_url)
    assert make_url(demo).database == f"{make_url(base_url).database}_demo"
    _make_table(demo, "old_run")
    assert fresh_db.recreate(base_url) == demo
    assert _tables(demo) == set()  # the second run starts clean
    assert _tables(base_url) == {"keep_me"}


def test_refuses_a_database_without_the_demo_suffix(base_url):
    _make_table(base_url, "keep_me")
    with pytest.raises(ValueError, match="_demo"):
        fresh_db.drop_and_create(base_url)
    assert _tables(base_url) == {"keep_me"}


def test_cli_prints_only_the_demo_url(base_url):
    out = subprocess.run(
        ["uv", "run", "python", "scripts/fresh_db.py", base_url],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == fresh_db.demo_url(base_url)
