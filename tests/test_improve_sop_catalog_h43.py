"""R9ih/dev-01 (H-43): the Improve prompt lists the SOPs in force; a wrong sop_id is sent back with valid ids."""

import json

from langgraph.types import Command

from backend.agent.nodes.improve import ProposalError
from tests.test_act import (
    CFG,
    HUMAN,
    SOP_ID,
    _tables,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    start,
    versions,
)

PLACEHOLDER = "PLACEHOLDER_NEEDS_VALID_SOP_ID"


def wrong_id():
    d = json.loads(improve_answer())
    d["sop_change"]["sop_id"] = PLACEHOLDER
    return json.dumps(d)


def improve_prompt(llm):
    call = llm.calls[-1]
    return call["system"] + "\n" + str(call["messages"][0]["content"])


def test_prompt_lists_every_sop_with_id_version_and_content_from_config(db_session):
    graph, llm = make(db_session, [*investigate_script(), improve_answer()], tables=_tables())
    start(graph, cfg_run())
    text = improve_prompt(llm)
    for s in CFG.sop:
        assert s.id in text
        assert s.steps[0] in text
        assert s.title in text
    assert "version" in text.lower()


def test_prompt_shows_the_new_version_after_a_sop_was_applied(db_session):
    graph, _ = make(db_session, [*investigate_script(), improve_answer()], tables=_tables())
    c = cfg_run()
    start(graph, c)
    graph.invoke(Command(resume=HUMAN), c)
    applied = versions(db_session)
    assert applied
    new_version, new_content = max(applied.items())

    graph2, llm2 = make(db_session, [*investigate_script(), improve_answer()], tables=_tables())
    start(graph2, cfg_run(), run_id="run_two")
    text = improve_prompt(llm2)
    assert new_content.splitlines()[-1] in text
    assert f'"version": {new_version}' in text or f"version {new_version}" in text


def test_prompt_tells_to_use_a_listed_id_and_full_new_content(db_session):
    graph, llm = make(db_session, [*investigate_script(), improve_answer()], tables=_tables())
    start(graph, cfg_run())
    low = improve_prompt(llm).lower()
    assert "one of" in low and "new_content" in low and "whole" in low


def test_prompt_cuts_long_sop_content_by_config_limit(db_session):
    long_cfg = CFG.model_copy(update={"sop": [
        CFG.sop[0].model_copy(update={"steps": ["x" * 5000, "TAILMARK"]}), *CFG.sop[1:],
    ]})
    graph, llm = make(db_session, [*investigate_script(), improve_answer()], tables=_tables(), cfg=long_cfg)
    start(graph, cfg_run())
    text = improve_prompt(llm)
    assert "TAILMARK" not in text
    assert "xxxxx" in text


def test_unknown_sop_id_is_sent_back_with_valid_ids_then_measured(db_session):
    graph, llm = make(db_session, [*investigate_script(), wrong_id(), improve_answer()], tables=_tables())
    c = cfg_run()
    start(graph, c)
    sent_back = str(llm.calls[-1]["messages"])
    assert "Rejected" in sent_back and PLACEHOLDER in sent_back
    assert all(s.id in sent_back for s in CFG.sop)
    out = graph.invoke(Command(resume=HUMAN), c)
    kpi = next(e for e in out["events"] if e["type"] == "kpi_measured")["payload"]
    assert kpi["status"] == "measured"


def test_unknown_sop_id_twice_error_lists_valid_ids(db_session):
    graph, _ = make(db_session, [*investigate_script(), wrong_id(), wrong_id()], tables=_tables())
    try:
        start(graph, cfg_run())
    except ProposalError as e:
        assert SOP_ID in str(e)
    else:
        raise AssertionError("expected ProposalError")
    assert versions(db_session) == {}
