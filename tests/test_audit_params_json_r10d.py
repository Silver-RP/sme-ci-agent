"""R10d/dev-02 (#113): audit_log.params is a JSON object, never the repr of a Python dict."""

import datetime as dt

import numpy as np
from sqlalchemy import text

from tests.test_act import (
    HUMAN,
    SOP_ID,
    approve,
    improve_answer,
    investigate_script,
    wrong_improve_answer,
)
from tests.test_api import _tables, make_client, start


def bad_strings(v, path="params"):
    """Every string (recursive) that looks like a Python repr of a dict/list of dicts."""
    if isinstance(v, str):
        return [(path, v)] if v.startswith(("{'", "[{'")) else []
    if isinstance(v, dict):
        return [b for k, x in v.items() for b in bad_strings(x, f"{path}.{k}")]
    if isinstance(v, list):
        return [b for i, x in enumerate(v) for b in bad_strings(x, f"{path}[{i}]")]
    return []


def audit_rows(client, run_id):
    r = client.get("/audit", params={"run_id": run_id, "limit": 500})
    assert r.status_code == 200
    return r.json()["rows"]


def assert_all_objects(rows):
    assert rows
    for row in rows:
        assert isinstance(row["params"], dict), row
        assert not bad_strings(row["params"]), (row["action"], bad_strings(row["params"]))


def full_run(client):
    run = start(client)
    assert approve(client, run["run_id"], HUMAN).json()["state"] == "finished"
    return run["run_id"]


def rollback_run(client):
    run = start(client)
    rid = run["run_id"]
    assert approve(client, rid, HUMAN).json()["pending"]["kind"] == "rollback"
    approve(client, rid, {"decision": "approved", "decided_by": "bob"})
    return rid


def test_every_audit_row_of_a_full_run_has_object_params(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    assert_all_objects(audit_rows(client, full_run(client)))


def test_every_audit_row_of_a_rollback_run_has_object_params(db_session):
    wrong = investigate_script("sensor calibration drift")
    script = [*wrong, wrong_improve_answer(), *wrong, wrong_improve_answer()]
    client = make_client(db_session, [script], tables=_tables())
    rows = audit_rows(client, rollback_run(client))
    assert_all_objects(rows)
    assert "rollback_done" in {r["action"] for r in rows} or "approval_decided" in {r["action"] for r in rows}


def test_save_learning_and_apply_sop_params_keep_their_structure(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    rid = full_run(client)
    rows = audit_rows(client, rid)
    learning = next(r for r in rows if r["action"] == "save_learning")
    saved = next(e for e in [m for m in client.get(f"/runs/{rid}/export").json()["events"]] if e["type"] == "learning_saved")
    assert set(learning["params"]["content"]) == set(saved["payload"]["content"])
    apply = next(r for r in rows if r["action"] == "apply_sop")
    assert isinstance(apply["params"]["approval"], dict) and "decided_by" in apply["params"]["approval"]


def test_old_string_params_row_is_still_read_verbatim(db_session):
    old = "{'k': 1}"
    db_session.execute(
        text("insert into audit_log (actor, action, params, run_id) values ('x', 'legacy', to_jsonb(cast(:p as text)), 'legacy_run')"),
        {"p": old},
    )
    db_session.commit()
    client = make_client(db_session, [])
    r = client.get("/audit", params={"run_id": "legacy_run"})
    assert r.status_code == 200
    assert r.json()["rows"][0]["params"] == old


def test_append_audit_converts_non_json_values(db_session):
    from backend.db import repo

    row = repo.append_audit(
        db_session, actor="a", action="x", run_id="r_json",
        params={"t": dt.datetime(2026, 1, 1, 9, tzinfo=dt.UTC), "n": np.float64(1.5), "i": np.int64(2), "a": np.array([1, 2]),
                "nan": float("nan"), "nested": {"d": dt.date(2026, 1, 2), "l": ({"k": np.bool_(True)},)}},
    )
    db_session.commit()
    p = row.params
    assert p["t"] == "2026-01-01T09:00:00+00:00" and p["n"] == 1.5 and p["i"] == 2 and p["a"] == [1, 2]
    assert p["nan"] is None and p["nested"] == {"d": "2026-01-02", "l": [{"k": True}]}
    assert SOP_ID
