"""R10e/dev-07 (H-66): the examples for the frontend are regenerated from the code, independent of the DB and the
clock, and their payload keys match docs/schema/payloads.md."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "schema" / "examples"
DASHBOARD = ROOT / "dashboard" / "fixtures" / "examples"
PAYLOADS = (ROOT / "docs" / "schema" / "payloads.md").read_text(encoding="utf-8")
ENGLISH = re.compile(r"\b(the|is|are|was|not|enough|evidence|should|please|Restore|Verify|Check)\b")


def load_script():
    spec = importlib.util.spec_from_file_location("export_fixtures_r10e", ROOT / "scripts" / "export_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return load_script()


def test_committed_examples_equal_a_fresh_export(mod, db_session, tmp_path):
    mod.export_all(tmp_path, db_session)
    names = sorted(p.name for p in tmp_path.glob("run-*.json"))
    assert names == sorted(p.name for p in EXAMPLES.glob("run-*.json"))
    for n in names:
        assert (EXAMPLES / n).read_text(encoding="utf-8") == (tmp_path / n).read_text(encoding="utf-8"), n


def test_command_twice_gives_the_same_bytes(mod, shared_db_url, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", shared_db_url)  # the command works on its own fresh database next to this one
    a, b = tmp_path / "a", tmp_path / "b"
    assert mod.main(["--out", str(a)]) == 0
    assert mod.main(["--out", str(b)]) == 0
    assert sorted(p.name for p in a.glob("run-*.json")) == sorted(p.name for p in EXAMPLES.glob("run-*.json"))
    for p in a.glob("run-*.json"):
        assert p.read_bytes() == (b / p.name).read_bytes() == (EXAMPLES / p.name).read_bytes(), p.name


def test_versions_and_learning_ids_do_not_depend_on_the_database(mod, db_session, tmp_path):
    mod.export_all(tmp_path / "a", db_session)  # the second export starts on a database that already has versions
    mod.export_all(tmp_path / "b", db_session)
    for p in (tmp_path / "a").glob("run-*.json"):
        a, b = json.loads(p.read_text()), json.loads((tmp_path / "b" / p.name).read_text())
        for d in (a, b):
            assert min(_versions(d)) == 1 if _versions(d) else True
        assert sorted(_versions(a)) == sorted(_versions(b)), p.name


def _versions(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("version") and isinstance(v, int):
                out.append(v)
            else:
                _versions(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _versions(v, out)
    return out


def test_dashboard_copy_is_byte_identical():
    names = sorted(p.name for p in EXAMPLES.glob("run-*.json"))
    assert names == sorted(p.name for p in DASHBOARD.glob("run-*.json"))
    for n in names:
        assert (EXAMPLES / n).read_bytes() == (DASHBOARD / n).read_bytes(), n


def test_normalize_is_idempotent_and_hides_ids_versions_and_times(mod):
    raw = {"events": [
        {"event_id": "evt_run_aaaaaaaa_0001", "run_id": "run_aaaaaaaa", "ts": "2030-05-05T10:00:07Z",
         "payload": {"version": 140, "base_version": 139, "proposal_id": "abcdef012345"}},
    ], "steps": []}
    out = mod.normalize(raw, "x")
    assert mod.normalize(out, "x") == out
    e = out["events"][0]
    assert e["run_id"] != "run_aaaaaaaa" and e["event_id"] == f"evt_{e['run_id']}_0001"
    assert (e["payload"]["base_version"], e["payload"]["version"]) == (1, 2)
    assert e["ts"].startswith("2026-01-01T") and e["payload"]["proposal_id"] != "abcdef012345"


def _events(branch):
    return json.loads((EXAMPLES / f"run-{branch}.json").read_text(encoding="utf-8"))["events"]


def test_insufficient_evidence_example_has_units_and_vietnamese_text():
    ev = next(e for e in _events("insufficient-evidence") if e["type"] == "kpi_measured")["payload"]
    assert ev["status"] == "insufficient_evidence" and ev["n_unit"] == "units" and ev["min_units_after"] > 0
    asked = [e["payload"]["question"] for e in _events("insufficient-evidence") if e["type"] == "question_asked"]
    assert asked and not any(ENGLISH.search(q) for q in asked), asked


def test_final_insufficient_evidence_example_is_a_halt_with_only_finish():
    events = _events("insufficient-evidence-final")
    kpi = next(e for e in events if e["type"] == "kpi_measured")["payload"]
    assert kpi["more_data_possible"] is False and kpi["n_unit"] == "units" and "min_units_after" in kpi
    halt = next(e["payload"] for e in events if e["type"] == "question_asked" and e["payload"].get("kind") == "halt")
    assert halt["reason"] == "insufficient_evidence" and halt["options"] == ["finish"]
    assert events[-1]["payload"]["status"] == "closed" and events[-1]["payload"]["reason"] == "closed_by_human"


def test_learning_saved_example_has_cause_status():
    content = next(e for e in _events("happy") if e["type"] == "learning_saved")["payload"]["content"]
    assert content["cause_status"] in ("confirmed", "unconfirmed") and content["outcome"] == "success"


def test_display_fields_in_examples_are_vietnamese():
    for p in EXAMPLES.glob("run-*.json"):
        for e in json.loads(p.read_text(encoding="utf-8"))["events"]:
            pl = e["payload"]
            texts = [pl.get("question")]
            texts += [pl.get("proposal", {}).get(k) for k in ("change", "rationale")]
            for t in texts:
                assert not (isinstance(t, str) and ENGLISH.search(t)), (p.name, t)


# ---- keys against docs/schema/payloads.md ----

def _section(event_type):
    m = re.search(rf"^### {event_type}\b.*?(?=^### |^## )", PAYLOADS, re.DOTALL | re.MULTILINE)
    assert m, event_type
    return m.group(0)


def _first_key_list(section):
    """The keys of the first one-line `{a, b, c}` in the section; `?` suffix marks optional ones."""
    line = next(s for s in section.splitlines() if re.match(r"^`\{.*\}`", s))
    inner = re.match(r"^`\{(.*)\}`", line).group(1)
    return [k.strip().split(":")[0] for k in re.split(r",\s*(?![^\[\]]*\])", inner) if k.strip()]


def _all_events():
    return [e for p in sorted(EXAMPLES.glob("run-*.json")) for e in json.loads(p.read_text(encoding="utf-8"))["events"]]


@pytest.mark.parametrize("etype", ["anomaly_detected", "kpi_measured"])
def test_example_payload_keys_match_the_documented_list(etype):
    documented = {k.rstrip("?") for k in _first_key_list(_section(etype))}
    seen = {k for e in _all_events() if e["type"] == etype for k in e["payload"]}
    optional = {"more_data_possible", "min_units_after", "min_samples_after", "reason"}
    assert seen - optional <= documented, seen - optional - documented
    assert documented - optional <= seen, documented - optional - seen  # a documented key missing from the examples


def test_every_payload_key_in_examples_is_named_in_its_section():
    for e in _all_events():
        section = _section(e["type"]) if e["type"] in {
            "tool_called", "anomaly_detected", "hypothesis_updated", "question_asked", "answer_received",
            "proposal_created", "approval_decided", "sop_applied", "kpi_measured", "rollback_done",
            "learning_saved", "run_finished"} else ""
        for k in e["payload"]:
            assert section and re.search(rf"\b{k}\b", section), (e["type"], k)


def test_learning_saved_content_keys_are_documented():
    section = _section("learning_saved")
    documented = set(re.findall(r"\w+", re.search(r"content: \{([^}]*)\}", section).group(1)))
    for e in _all_events():
        if e["type"] == "learning_saved":
            assert set(e["payload"]["content"]) <= documented, set(e["payload"]["content"]) - documented
            assert "cause_status" in documented and "cause_status" in e["payload"]["content"]
