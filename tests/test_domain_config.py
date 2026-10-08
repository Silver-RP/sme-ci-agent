import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from backend.domain_config import DEFAULT_PROFILE_PATH, DomainConfig, load_domain_config

ROOT = Path(__file__).resolve().parents[1]


def _valid() -> dict:
    return yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))


def _write(tmp_path, data) -> Path:
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_load_real_file():
    cfg = load_domain_config()
    assert isinstance(cfg, DomainConfig)
    assert cfg.domain == "manufacturing"
    assert cfg.kpis and cfg.hypothesis_groups and cfg.sop
    assert "machine" in cfg.hypothesis_groups
    assert cfg.kpis[0].target > 0


@pytest.mark.parametrize("field", ["domain", "kpis", "hypothesis_groups", "sop", "approvers"])
def test_missing_required_field(tmp_path, field):
    data = _valid()
    del data[field]
    with pytest.raises(ValidationError, match=field):
        load_domain_config(_write(tmp_path, data))


def test_wrong_type(tmp_path):
    data = _valid()
    data["kpis"][0]["target"] = "not-a-number"
    with pytest.raises(ValidationError, match="target"):
        load_domain_config(_write(tmp_path, data))


def test_sop_requires_id_and_version(tmp_path):
    cfg = load_domain_config()
    assert cfg.sop[0].id and cfg.sop[0].version >= 1
    data = _valid()
    del data["sop"][0]["version"]
    with pytest.raises(ValidationError, match="version"):
        load_domain_config(_write(tmp_path, data))


def test_no_hardcoded_names_in_code():
    cfg = load_domain_config()
    names = {k.name for k in cfg.kpis} | set(cfg.hypothesis_groups)
    for g in cfg.hypothesis_groups.values():
        names |= set(g)
    src = (ROOT / "backend" / "domain_config.py").read_text(encoding="utf-8")
    for n in names:
        assert not re.search(rf"\b{re.escape(n)}\b", src), n


def test_approvers_loaded_and_resolved():
    cfg = load_domain_config()
    assert cfg.approvers
    assert cfg.resolve_approver(f"  {cfg.approvers[0].upper()} ") == cfg.approvers[0]
    for bad in ["", "   ", None, "llm", "nobody"]:
        assert cfg.resolve_approver(bad) is None


@pytest.mark.parametrize("val", [[], ["alice", " "]])
def test_approvers_must_be_non_empty_names(tmp_path, val):
    data = _valid()
    data["approvers"] = val
    with pytest.raises(ValidationError):
        load_domain_config(_write(tmp_path, data))


SCENARIO1 = ROOT / "data" / "scenarios" / "scenario1.yaml"


def test_sop_for_scenario1_names_the_scenario_setpoint_parameter():
    """H-10: the SOP used by scenario 1 must talk about the scenario's own setpoint parameter."""
    scenario = yaml.safe_load(SCENARIO1.read_text(encoding="utf-8"))
    parameter = scenario["injected_anomalies"][0]["trace"]["parameter"]
    reference = scenario["baseline"][parameter]
    sop = load_domain_config().sop[0]
    text = "\n".join(sop.steps)
    assert parameter in text
    assert str(reference) in text
    assert "barrel" not in text.lower()


def test_domain_values_come_from_yaml_not_code():
    """H-22: signal names, setpoint event, default period and demo machine live in the YAML."""
    cfg = load_domain_config()
    scenario = yaml.safe_load(SCENARIO1.read_text(encoding="utf-8"))
    names = {cfg.signals.setpoint_deviation, cfg.signals.batch_change, cfg.signals.setpoint_event}
    names |= {cfg.demo.machine_id, *cfg.default_period}
    names |= {s for s in scenario["plant"]["machines"] if s == cfg.demo.machine_id}
    assert all(names)
    files = [
        ROOT / "backend" / "tools" / "readonly.py",
        ROOT / "backend" / "agent" / "graph.py",
        ROOT / "backend" / "agent" / "demo_llm.py",
        ROOT / "backend" / "domain_config.py",
    ]
    for f in files:
        src = f.read_text(encoding="utf-8")
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith(("#", '"""')))
        for n in names | {"wrong_setpoint", "material_batch", "setpoint_change", "M02", "2026-10-01", "2026-10-07"}:
            assert not re.search(rf"[\"']{re.escape(n)}[\"']", code), (f.name, n)
