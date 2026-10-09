"""R9h/dev-02: scripts load .env for --llm real, fail clearly when config is missing, and checkpoints do not warn."""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

from backend.agent.llm import prepare_real_llm_env
from backend.domain_config import load_domain_config
from tests.test_e2e import e2e_db_url  # noqa: F401  (fixture)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_r9h", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "MODEL_REASONING"):
        monkeypatch.delenv(k, raising=False)


def test_env_file_is_loaded(tmp_path, clean_env):
    f = tmp_path / ".env"
    f.write_text("ANTHROPIC_API_KEY=fake-key\nMODEL_REASONING=fake-model\n")
    assert prepare_real_llm_env(f) is None
    import os

    assert os.environ["MODEL_REASONING"] == "fake-model"
    del os.environ["ANTHROPIC_API_KEY"], os.environ["MODEL_REASONING"]


def test_existing_env_is_not_overridden(tmp_path, clean_env, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("ANTHROPIC_API_KEY=from-file\nMODEL_REASONING=from-file\n")
    monkeypatch.setenv("MODEL_REASONING", "from-shell")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-from-shell")
    assert prepare_real_llm_env(f) is None
    import os

    assert os.environ["MODEL_REASONING"] == "from-shell"
    assert os.environ["ANTHROPIC_API_KEY"] == "key-from-shell"


def test_missing_vars_message_names_them_without_values(tmp_path, clean_env):
    f = tmp_path / ".env"
    f.write_text("ANTHROPIC_API_KEY=secret-value\n")
    msg = prepare_real_llm_env(f)
    assert "MODEL_REASONING" in msg and "ANTHROPIC_API_KEY" not in msg and "secret-value" not in msg
    import os

    os.environ.pop("ANTHROPIC_API_KEY", None)


def test_missing_env_file_and_vars(tmp_path, clean_env):
    msg = prepare_real_llm_env(tmp_path / "nope.env")
    assert "ANTHROPIC_API_KEY" in msg and "MODEL_REASONING" in msg


@pytest.mark.parametrize("name", ["eval_rootcause", "run_scenario"])
def test_script_real_without_config_exits_nonzero_no_traceback(name, tmp_path, clean_env, monkeypatch, capsys):
    mod = load_script(name)
    monkeypatch.setattr(mod, "ROOT", tmp_path)  # a temp dir with no .env: the real .env is never read
    rc = mod.main(["--llm", "real"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "ANTHROPIC_API_KEY" in err and "MODEL_REASONING" in err
    assert "Traceback" not in err


def test_eval_scripted_has_no_deserializing_warning(db_session, caplog):
    from langgraph.checkpoint.serde import jsonplus

    getattr(jsonplus, "_warned_unregistered_types", set()).clear()  # the library warns once per process
    mod = load_script("eval_rootcause")
    with caplog.at_level(logging.WARNING):
        mod.evaluate({"right": mod.SCRIPTED["right"]}, load_domain_config(), db_session, seeds=[42])
    assert not [r for r in caplog.records if "Deserializing" in r.getMessage()]
