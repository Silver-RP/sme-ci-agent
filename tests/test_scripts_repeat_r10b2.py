"""R10b2/dev-03 (rework): the real script, run twice on one database WITHOUT SME_SKIP_HANDLED=0 in the caller's
env, must reach learning_saved both times (the scripted LLM is written for the first anomaly)."""

import os
import subprocess
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.db.config import get_database_url
from tests.conftest import ROOT


@pytest.fixture
def own_db_url():
    base = make_url(get_database_url())
    name = f"{base.database}_rpt_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield url
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_run_scenario_twice_on_one_db_without_skip_env(own_db_url):
    env = {k: v for k, v in os.environ.items() if k != "SME_SKIP_HANDLED"}
    env["DATABASE_URL"] = own_db_url
    for i in (1, 2):
        r = subprocess.run(["uv", "run", "python", "scripts/run_scenario.py"], cwd=ROOT, env=env,
                           capture_output=True, text=True, check=False)
        assert r.returncode == 0, f"run {i}: {r.stdout[-800:]}\n{r.stderr[-800:]}"
        assert "learning_saved" in r.stdout, f"run {i}: {r.stdout[-800:]}"
