"""R10b1/dev-07: scripts/gen_data.py --out-dir writes the contract CSV (5 tables, no answer key) and the
generate -> check -> import -> run round trip works on the real pipeline (scripted LLM, no mocks)."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import _default_tables, create_app
from backend.dataset_store import SOURCE_TABLES, apply_to_config
from backend.domain_config import load_domain_config
from backend.sandbox.validate import Validation, read_directory
from backend.tools.readonly import ToolContext
from tests.test_demo_llm_branches_r10a import ANSWER, decide, event_types, get

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_r10b1_dev07", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


gen_data = _load("gen_data")
import_data = _load("import_data")


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("export") / "export"
    gen_data.main(["--seed", "42", "--out-dir", str(out)])
    return out


def test_out_dir_holds_exactly_the_contract_tables(exported):
    assert {p.name for p in exported.iterdir()} == {f"{t}.csv" for t in SOURCE_TABLES}


def test_contract_text_formats(exported):
    prod = (exported / "production_log.csv").read_text(encoding="utf-8").splitlines()
    assert prod[0].split(",")[:3] == ["shift_start", "shift", "machine_id"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", prod[1].split(",")[0])
    sched = pd.read_csv(exported / "shift_schedule.csv", dtype=str)
    assert sched["is_substitute"].isin(["true", "false"]).all()
    assert sched["date"].str.fullmatch(r"\d{4}-\d\d-\d\d").all()
    p = pd.read_csv(exported / "production_log.csv", dtype=str)
    assert p["units_produced"].str.fullmatch(r"\d+").all() and p["units_nonconforming"].str.fullmatch(r"\d+").all()
    assert not (exported / "production_log.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_export_passes_the_validator_with_zero_errors(exported):
    tables, extras = read_directory(exported)
    issues = Validation(tables, list(extras), load_domain_config()).run()
    assert [i for i in issues if i["severity"] == "error"] == []
    assert import_data.main([str(exported), "--check-only"]) == 0


def test_export_has_no_answer_key(exported, tmp_path):
    truth_file = Path(str(exported) + "_ground_truth.json")
    assert truth_file.is_file()  # beside the export, not inside it
    truth = json.loads(truth_file.read_text(encoding="utf-8"))
    assert {t["id"] for t in truth} == {"A1", "A2_recurrence", "FP1"}
    banned_cols = {"root_cause", "hidden", "planned", "correct_fix", "effect_value", "ground_truth", "label"}
    secrets = {t["root_cause"] for t in truth} | {t["correct_fix"] for t in truth if t["correct_fix"]}
    for f in exported.iterdir():
        text = f.read_text(encoding="utf-8")
        assert not (banned_cols & set(text.splitlines()[0].split(","))), f.name
        for s in secrets:
            assert s.lower() not in text.lower(), (f.name, s)
        assert "wrong setpoint" not in text.lower() and "wrong_setpoint" not in text.lower()
    notes = pd.read_csv(exported / "machine_log.csv", dtype=str)["note"].dropna()
    assert not notes.str.contains(r"root.?cause|wrong|mistake|error|fault|drift|calibrat", case=False).any()
    assert not any(f.name.startswith("ground_truth") for f in exported.iterdir())


def test_explicit_ground_truth_path_and_repeat_calls(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gt = tmp_path / "answers" / "gt.json"
    gen_data.main(["--seed", "7", "--out-dir", str(a), "--ground-truth", str(gt)])
    gen_data.main(["--seed", "7", "--out-dir", str(b)])
    assert gt.is_file()
    for t in SOURCE_TABLES:
        assert (a / f"{t}.csv").read_bytes() == (b / f"{t}.csv").read_bytes()
    assert gt.read_text() == Path(str(b) + "_ground_truth.json").read_text()


def test_round_trip_to_learning_saved(exported, tmp_path, monkeypatch, db_session):
    monkeypatch.setenv("SME_DATASETS_DIR", str(tmp_path / "datasets"))
    monkeypatch.delenv("SME_DATASET", raising=False)
    assert import_data.main([str(exported), "--check-only"]) == 0
    assert import_data.main([str(exported), "--name", "t"]) == 0
    monkeypatch.setenv("SME_DATASET", "t")
    monkeypatch.setenv("SME_LLM", "scripted")
    monkeypatch.delenv("SME_DEMO_SCENARIO", raising=False)
    cfg = apply_to_config(load_domain_config())

    def ctx_factory(run_id):
        return ToolContext(tables=_default_tables(), session=db_session, run_id=run_id, config=cfg)

    c = TestClient(create_app(cfg, ctx_factory=ctx_factory))
    r = c.post("/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    if run["pending"] and run["pending"]["type"] == "answer":
        qid = run["pending"]["question_id"]
        run = c.post(f"/runs/{run['run_id']}/answer", json={**ANSWER, "question_id": qid}).json()
    assert run["pending"]["kind"] == "proposal", run
    rid = run["run_id"]
    human = {"decision": "approved", "decided_by": "alice", "reason": "ok"}
    assert decide(c, rid, human)["state"] == "finished"
    types = event_types(c, rid)
    assert "anomaly_detected" in types and "learning_saved" in types
    assert get(c, rid)["state"] == "finished"
