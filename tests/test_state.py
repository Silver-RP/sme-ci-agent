import pytest
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from backend.agent import state as state_mod
from backend.agent.state import AgentState, Hypothesis, new_state, validate_hypothesis_groups
from backend.domain_config import load_domain_config


def test_empty_state():
    s = new_state()
    assert s["hypotheses"] == [] and s["evidence"] == [] and s["events"] == []
    assert s["anomaly"] is None and s["proposal"] is None


def test_full_state_works_in_stategraph():
    def node(st):
        return {"events": [{"type": "x"}]}

    g = StateGraph(AgentState)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    full = AgentState(
        run_id="r1",
        domain="manufacturing",
        anomaly={"kpi": "error_rate", "z": 3.2},
        hypotheses=[Hypothesis(group="machine", description="wear", confidence=0.6)],
        evidence=[{"source": "log", "value": 1}],
        proposal={"sop_id": "SOP-INJ-001"},
        events=[],
    )
    out = g.compile().invoke(full)
    assert out["hypotheses"][0].group == "machine"
    assert out["events"] == [{"type": "x"}]
    assert out["proposal"] == {"sop_id": "SOP-INJ-001"}


def test_no_defect_names():
    names = list(AgentState.__annotations__) + list(Hypothesis.model_fields)
    names += [n for n in dir(state_mod) if not n.startswith("__")]
    assert not [n for n in names if "defect" in n.lower()]


@pytest.mark.parametrize("c", [0.0, 1.0, 0.5])
def test_confidence_boundaries_ok(c):
    assert Hypothesis(group="machine", description="d", confidence=c).confidence == c


@pytest.mark.parametrize("c", [-0.001, 1.001])
def test_confidence_out_of_range(c):
    with pytest.raises(ValidationError):
        Hypothesis(group="machine", description="d", confidence=c)


def test_group_matches_yaml_keys():
    cfg = load_domain_config()
    validate_hypothesis_groups([Hypothesis(group="method", description="d", confidence=0.1)], cfg)
    with pytest.raises(ValueError):
        validate_hypothesis_groups([Hypothesis(group="nope", description="d", confidence=0.1)], cfg)
