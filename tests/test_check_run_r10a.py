"""R10a/dev-07 (H-26): scripts/check_run.py walks a whole run over HTTP and checks the read APIs.
Uses a Starlette TestClient (same call shape as httpx.Client); no network."""

import importlib.util
import sys
from pathlib import Path

import pytest

from tests.test_demo_llm_branches_r10a import CFG, make_client

SPEC = importlib.util.spec_from_file_location("check_run_r10a", Path(__file__).resolve().parents[1] / "scripts" / "check_run.py")
check_run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_run
SPEC.loader.exec_module(check_run)

KPI, SOP = CFG.kpis[0].name, CFG.sop[0].id


def test_passes_and_repeat_is_clean(db_session, monkeypatch, capsys):
    c = make_client(db_session, monkeypatch)
    assert check_run.check_many(c, KPI, SOP, repeat=2) is True  # second run: no state leaks from the first
    out = capsys.readouterr().out
    assert "reached learning_saved" in out and "CHECK PASSED" in out
    assert "passed 2/2; p95" in out and "run 1/2:" in out and "run 2/2:" in out


def test_one_run_prints_no_p95(db_session, monkeypatch, capsys):
    c = make_client(db_session, monkeypatch)
    assert check_run.check_many(c, KPI, SOP) is True
    assert "p95" not in capsys.readouterr().out


def test_broken_step_names_the_step(db_session, monkeypatch, capsys):
    c = make_client(db_session, monkeypatch)
    assert check_run.check_many(c, "no_such_kpi", SOP) is False  # /kpi/series answers 422
    err = capsys.readouterr().err
    assert "CHECK FAILED: GET /kpi/series" in err


def test_unknown_sop_fails_on_sop_step(db_session, monkeypatch, capsys):
    c = make_client(db_session, monkeypatch)
    assert check_run.check_many(c, KPI, "no_such_sop") is False
    assert "CHECK FAILED: GET /sop/no_such_sop/versions" in capsys.readouterr().err


def test_wrong_url_fails_with_nonzero_exit(capsys):
    assert check_run.main(["--api", "http://127.0.0.1:9"]) == 1
    assert "CHECK FAILED:" in capsys.readouterr().err


def test_p95():
    assert check_run.p95([]) == 0.0
    assert check_run.p95([1.0]) == 1.0
    assert check_run.p95([float(i) for i in range(1, 11)]) == 10.0
    with pytest.raises(SystemExit):
        check_run.main(["--api", "x", "--repeat", "0"])
