"""H-30: action value/machine are checked against the domain config before a proposal exists."""

import json
import math

import pytest

from backend.agent.nodes.improve import ProposalError, parse_proposal
from backend.domain_config import load_domain_config

CFG = load_domain_config()
PARAM = CFG.actions.parameters[0]
EVIDENCE = [{"source": "tool", "tool": "correlate", "result": {"r": 0.9}}]
ANOMALY = {"kpi": CFG.kpis[0].name, "machine": "M02"}


def text(cfg=CFG, **action):
    action = {"parameter": PARAM, "machine_id": "M02", "value": 180, **action}
    return json.dumps(
        {
            "change": "c",
            "rationale": "r",
            "evidence_refs": [0],
            "expected_kpi": {"kpi": cfg.kpis[0].name, "direction": "decrease", "target": 0.02},
            "sop_change": {"sop_id": cfg.sop[0].id, "new_content": "x"},
            "action": action,
        }
    )


def raw_value(v: str) -> str:
    return text().replace('"value": 180', f'"value": {v}')


@pytest.mark.parametrize("v", ["NaN", "Infinity", "-Infinity", "1e9", "-1000"])
def test_improve_rejects_out_of_range_action(v):
    with pytest.raises(ProposalError):
        parse_proposal(raw_value(v), EVIDENCE, CFG, ANOMALY)


def test_improve_rejects_foreign_machine():
    with pytest.raises(ProposalError, match="M99"):
        parse_proposal(text(machine_id="M99"), EVIDENCE, CFG, ANOMALY)


def test_boundaries_accepted():
    lim = CFG.actions.limits[PARAM]
    for v in (lim.min, lim.max):
        d = parse_proposal(text(value=v), EVIDENCE, CFG, ANOMALY)
        assert d.action.value == v and math.isfinite(d.action.value)


def test_just_outside_boundaries_rejected():
    lim = CFG.actions.limits[PARAM]
    for v in (lim.min - 0.01, lim.max + 0.01):
        with pytest.raises(ProposalError):
            parse_proposal(text(value=v), EVIDENCE, CFG, ANOMALY)


def test_range_comes_from_config():
    from backend.domain_config import ActionLimit

    cfg = CFG.model_copy(
        update={
            "actions": CFG.actions.model_copy(
                update={"limits": {**CFG.actions.limits, PARAM: ActionLimit(min=10, max=20)}}
            )
        }
    )
    assert parse_proposal(text(value=15), EVIDENCE, cfg, ANOMALY).action.value == 15
    with pytest.raises(ProposalError):
        parse_proposal(text(value=180), EVIDENCE, cfg, ANOMALY)


def test_every_parameter_has_limit_in_yaml():
    assert set(CFG.actions.limits) == set(CFG.actions.parameters)


def test_no_anomaly_machine_skips_machine_check_only():
    d = parse_proposal(text(machine_id="M05"), EVIDENCE, CFG, {"kpi": "x"})
    assert d.action.machine_id == "M05"
    d = parse_proposal(text(machine_id="M05"), EVIDENCE, CFG)
    assert d.action.machine_id == "M05"
