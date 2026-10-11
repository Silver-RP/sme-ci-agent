"""R10b1/dev-06: scripts/import_data.py, named datasets, SME_DATASET wiring (tables and base SOP)."""

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import _default_tables, create_app
from backend.dataset_store import DatasetError, active_tables, load_tables
from backend.domain_config import load_domain_config
from backend.tools.actions import _write_sop_version
from backend.tools.readonly import ToolContext, read_sop

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "data" / "templates" / "valid"
INVALID = ROOT / "data" / "templates" / "invalid"

_spec = importlib.util.spec_from_file_location("import_data_r10b1", ROOT / "scripts" / "import_data.py")
import_data = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = import_data
_spec.loader.exec_module(import_data)

NEW_SOP = (
    "sop_id,version,title,step_no,step_text\n"
    "SOP-RFL-001,1,Reflow imported,1,Check the oven\n"
    "SOP-RFL-001,1,Reflow imported,2,Log the profile\n"
    "SOP-IMP-777,1,Only in the dataset,1,Do the thing\n"
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "datasets"
    monkeypatch.setenv("SME_DATASETS_DIR", str(root))
    monkeypatch.delenv("SME_DATASET", raising=False)
    return root


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    shutil.copytree(VALID, d)
    return d


def digest(d: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


def lines(p: Path) -> int:
    return len(p.read_text(encoding="utf-8").strip().splitlines()) - 1


def test_valid_template_imports(store, src):
    before = digest(src)
    assert import_data.main([str(src), "--name", "ok"]) == 0
    assert (store / "ok" / "_COMPLETE").is_file()
    assert digest(src) == before  # source untouched
    assert {p.name for p in (store / "ok").iterdir()} == {*(p.name for p in VALID.iterdir()), "_COMPLETE"}


def test_errors_exit_nonzero_and_create_nothing(store, tmp_path, capsys):
    bad = tmp_path / "bad"
    shutil.copytree(INVALID / "V03_negative_count", bad)
    assert import_data.main([str(bad), "--name", "bad"]) == 1
    out = capsys.readouterr().out
    assert "V03" in out and "production_log" in out
    assert not store.exists() or list(store.iterdir()) == []


def test_check_only_writes_nothing(store, src, capsys):
    assert import_data.main([str(src), "--check-only", "--name", "x"]) == 0
    assert not store.exists()
    out = capsys.readouterr().out
    assert "production_log: 9" in out  # report shows row counts


def test_warnings_only_still_imports(store, src, capsys):
    (src / "kpi_log.csv").write_text("a,b\n1,2\n", encoding="utf-8")  # N01 warning
    assert import_data.main([str(src), "--name", "warn"]) == 0
    assert "N01" in capsys.readouterr().out
    assert (store / "warn" / "_COMPLETE").is_file()
    assert not (store / "warn" / "kpi_log.csv").exists()  # file outside the contract is not copied


def test_missing_directory_and_bad_name_and_existing_name(store, src, tmp_path):
    assert import_data.main([str(tmp_path / "nope")]) == 2
    assert import_data.main([str(src), "--name", "../evil"]) == 2
    assert import_data.main([str(src), "--name", "dup"]) == 0
    assert import_data.main([str(src), "--name", "dup"]) == 2  # never overwrite
    assert not [p for p in store.iterdir() if p.name.startswith(".")]  # no temp leftovers


def test_interrupted_write_leaves_no_dataset(store, src, monkeypatch):
    def boom(self, target):
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "rename", boom)
    with pytest.raises(KeyboardInterrupt):
        import_data.main([str(src), "--name", "half"])
    monkeypatch.undo()
    assert not (store / "half").exists()
    assert not [p for p in store.iterdir()]  # temp dir cleaned up
    monkeypatch.setenv("SME_DATASETS_DIR", str(store))
    monkeypatch.setenv("SME_DATASET", "half")
    with pytest.raises(DatasetError, match="not found"):
        load_domain_config()


def test_dataset_without_marker_is_refused(store, src, monkeypatch):
    assert import_data.main([str(src), "--name", "cut"]) == 0
    (store / "cut" / "_COMPLETE").unlink()  # as if the process died before the end
    monkeypatch.setenv("SME_DATASET", "cut")
    for call in (load_domain_config, lambda: active_tables(dict), lambda: load_tables("cut")):
        with pytest.raises(DatasetError, match="incomplete"):
            call()


def test_unset_dataset_means_simulator_and_config_sop(store):
    cfg = load_domain_config()
    assert {s.origin for s in cfg.sop} == {"config"}
    assert active_tables(lambda: "simulator") == "simulator"


def test_dataset_tables_and_sop_follow_env(store, src, monkeypatch):
    (src / "sop.csv").write_text(NEW_SOP, encoding="utf-8")
    assert import_data.main([str(src), "--name", "t"]) == 0
    monkeypatch.setenv("SME_DATASET", "t")

    tables = _default_tables()
    assert len(tables["production_log"]) == lines(src / "production_log.csv")
    assert len(tables["machine_log"]) == lines(src / "machine_log.csv")
    assert len(tables["shift_schedule"]) == lines(src / "shift_schedule.csv")
    assert len(tables["material_batches"]) == lines(src / "material_batches.csv")
    cfg = load_domain_config()
    n_kpi = len(cfg.kpis)
    assert len(tables["kpi_log"]) == n_kpi * lines(src / "production_log.csv")  # derived, no zero-unit rows here
    assert pd.api.types.is_datetime64_any_dtype(tables["production_log"]["shift_start"])
    assert tables["shift_schedule"]["is_substitute"].dtype == bool
    assert set(tables) == set(load_tables("t"))

    ids = {s.id for s in cfg.sop}
    assert ids == {"SOP-RFL-001", "SOP-IMP-777"}  # SOP-CAL-002 is only in the config: not in the dataset
    rfl = next(s for s in cfg.sop if s.id == "SOP-RFL-001")
    assert rfl.title == "Reflow imported" and rfl.steps == ["Check the oven", "Log the profile"]
    assert rfl.origin == "import"

    monkeypatch.delenv("SME_DATASET")
    assert {s.id for s in load_domain_config().sop} >= {"SOP-CAL-002"}


def test_dataset_without_optional_batches_and_repeat_calls(store, src, monkeypatch):
    (src / "material_batches.csv").unlink()
    assert import_data.main([str(src), "--name", "nb"]) == 0
    monkeypatch.setenv("SME_DATASET", "nb")
    a, b = load_tables("nb"), load_tables("nb")
    assert len(a["material_batches"]) == 0 and len(a["production_log"]) == len(b["production_log"]) > 0
    assert set(a["material_batches"].columns) == set(b["material_batches"].columns)


def test_dataset_with_zero_units_row(store, src, monkeypatch):
    p = src / "production_log.csv"
    rows = p.read_text(encoding="utf-8").splitlines()
    first = rows[1].split(",")
    first[3], first[4], first[5] = "0", "0", "0"
    rows[1] = ",".join(first)
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert import_data.main([str(src), "--name", "z"]) == 0
    monkeypatch.setenv("SME_DATASET", "z")
    cfg = load_domain_config()
    assert len(load_tables("z")["kpi_log"]) == len(cfg.kpis) * (lines(p) - 1)


def test_api_sop_versions_show_import_origin(store, src, monkeypatch, db_session):
    (src / "sop.csv").write_text(NEW_SOP, encoding="utf-8")
    assert import_data.main([str(src), "--name", "api"]) == 0
    monkeypatch.setenv("SME_DATASET", "api")
    cfg = load_domain_config()

    def ctx_factory(run_id):
        return ToolContext(tables=_default_tables(), session=db_session, run_id=run_id, config=cfg)

    client = TestClient(create_app(cfg, llm_factory=lambda rid: None, ctx_factory=ctx_factory))
    versions = client.get("/sop/SOP-RFL-001/versions").json()["versions"]
    assert [(v["version"], v["created_by"], v["run_id"], v["created_at"]) for v in versions] == [(1, "import", None, None)]
    assert versions[0]["content"] == "Check the oven\nLog the profile"
    assert client.get("/sop/SOP-IMP-777/versions").status_code == 200
    assert client.get("/sop/SOP-CAL-002/versions").status_code == 404  # config-only SOP is not in the dataset

    ctx = ToolContext(tables=_default_tables(), session=db_session, run_id="r1", config=cfg)
    assert read_sop(ctx, sop_id="SOP-RFL-001")["content"] == "Check the oven\nLog the profile"
    _write_sop_version(ctx, "SOP-RFL-001", "New step", "Linh")  # first DB write keeps the imported base row
    db_session.flush()
    versions = client.get("/sop/SOP-RFL-001/versions").json()["versions"]
    assert [(v["version"], v["created_by"]) for v in versions] == [(1, "import"), (2, "Linh")]
    assert versions[0]["run_id"] is None and versions[0]["created_at"] is None
