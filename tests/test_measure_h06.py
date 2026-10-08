"""R9/dev-02 (H-06): Measure follows the structured action the person approved, not the words of a hypothesis.

Raw data keeps the anomaly (``_tables``), so only the simulated post-change data can fix it. No network, seed 42.
"""

import json

import pytest
import yaml
from langgraph.types import Command

from backend.agent.nodes.improve import ProposalError
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH
from tests.test_act import (
    CFG,
    CHANGE,
    HUMAN,
    _tables,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    start,
    types,
)
from tests.test_api import make_client

SCENARIO = yaml.safe_load(DEFAULT_SCENARIO_PATH.read_text(encoding="utf-8"))
ANOMALY = SCENARIO["injected_anomalies"][0]
PARAM = ANOMALY["trace"]["parameter"]
SOP_VALUE = SCENARIO["baseline"][PARAM]
MACHINE = ANOMALY["machine"]
NEGATIVE = "Setpoint is NOT the cause; material batch"


def answer(action="default", **action_fields):
    """An Improve answer with a structured action (``action=None`` -> no action at all)."""
    d = json.loads(improve_answer())
    if action == "default":
        action = {"parameter": PARAM, "machine_id": MACHINE, "value": SOP_VALUE, **action_fields}
    if action is None:
        d.pop("action", None)
    else:
        d["action"] = action
    return json.dumps(d)


def script(improve, description="wrong_setpoint"):
    s = investigate_script()
    d = json.loads(s[1])
    d["hypotheses"][0]["description"] = description
    return [s[0], json.dumps(d), improve]


def run(db_session, improve, description="wrong_setpoint"):
    graph, _ = make(db_session, script(improve, description), tables=_tables())
    c = cfg_run()
    start(graph, c)
    return graph, c, graph.invoke(Command(resume=HUMAN), c)


def test_negative_hypothesis_without_a_setpoint_change_does_not_pass(db_session):
    # H-06: the words "setpoint ... NOT the cause" used to count as a correct fix
    _, _, out = run(db_session, answer(machine_id="M01"), NEGATIVE)
    assert out["measurement"]["passed"] is False
    _, _, out = run(db_session, answer(action=None), NEGATIVE)
    assert out["measurement"]["status"] == "not_applied" and out["measurement"]["passed"] is None


def test_hypothesis_words_do_not_decide_the_result(db_session):
    _, _, out = run(db_session, answer(), "sensor calibration drift")  # right action, unrelated words
    assert out["measurement"]["passed"] is True


def test_restoring_the_sop_value_passes(db_session):
    _, _, out = run(db_session, answer(value=SOP_VALUE))
    m = out["measurement"]
    assert m["passed"] is True and abs(m["after"] - CFG.kpis[0].target) < 0.005
    assert "learning_saved" in types(out)


def test_partial_fix_follows_the_yaml_threshold(db_session):
    _, _, out = run(db_session, answer(value=SOP_VALUE + 10))
    m = out["measurement"]
    limit = CFG.kpis[0].target * (1 + CFG.measure.tolerance)
    assert m["before"] > m["after"] > limit  # KPI drops part of the way, still above the YAML limit
    assert m["passed"] is False


def test_wrong_machine_or_unmodelled_parameter_does_not_pass(db_session):
    _, _, out = run(db_session, answer(machine_id="M03"))
    assert out["measurement"]["passed"] is False
    _, _, out = run(db_session, answer(parameter="other_parameter_c"))
    assert out["measurement"]["passed"] is False


def test_sop_applied_payload_does_not_leak_the_simulator_verdict(db_session):
    _, _, out = run(db_session, answer())
    payload = next(e for e in out["events"] if e["type"] == "sop_applied")["payload"]
    assert "sim" not in payload and "fixed" not in json.dumps(payload)
    assert payload["action"] == {"parameter": PARAM, "machine_id": MACHINE, "value": SOP_VALUE}


def test_source_data_untouched_and_repeat_gives_same_result(db_session):
    tables = _tables()
    before = tables["kpi_log"].copy()
    afters = []
    for _ in range(2):
        graph, _ = make(db_session, script(answer()), tables=tables)
        c = cfg_run()
        start(graph, c)
        afters.append(graph.invoke(Command(resume=HUMAN), c)["measurement"]["after"])
    assert afters[0] == afters[1]
    assert tables["kpi_log"].equals(before)


# ---- unknown parameter from the LLM: ask again (bounded), then a clear error ----


def test_unknown_parameter_is_sent_back_to_the_llm_once(db_session):
    graph, llm = make(db_session, [*script(answer(parameter="made_up_param"))[:2], answer(parameter="made_up_param"), answer()], tables=_tables())
    c = cfg_run()
    start(graph, c)
    assert graph.get_state(c).next == ("wait_approval",)
    assert any("made_up_param" in str(m) for call in llm.calls[-1:] for m in call["messages"])


def test_unknown_parameter_twice_is_a_clear_error(db_session):
    bad = answer(parameter="made_up_param")
    graph, _ = make(db_session, [*script(bad)[:2], bad, bad], tables=_tables())
    with pytest.raises(ProposalError, match="made_up_param"):
        start(graph, cfg_run())


def test_unknown_parameter_puts_the_api_run_in_error_state(db_session):
    bad = answer(parameter="made_up_param")
    client = make_client(db_session, [script(bad) + [bad]], tables=_tables())
    r = client.post("/runs", json={"change_time": CHANGE})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["state"] == "error" and "made_up_param" in body["error"]
    assert client.get(f"/runs/{body['run_id']}").json()["state"] == "error"


def test_valid_parameters_come_from_the_yaml():
    assert PARAM in CFG.actions.parameters
