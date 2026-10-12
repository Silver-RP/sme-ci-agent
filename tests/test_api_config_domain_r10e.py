"""R10e/dev-05: read-only GET /config/domain (#114)."""

import json

from sqlalchemy import func, select

from backend.db.models import AuditLog, SopVersion
from tests.test_act import CFG, HUMAN, SOP_ID, approve, improve_answer, investigate_script
from tests.test_api import make_client, start


def total_rows(session):
    return (
        session.scalar(select(func.count()).select_from(AuditLog)),
        session.scalar(select(func.count()).select_from(SopVersion)),
    )


def test_shape_and_values_match_config(db_session, monkeypatch):
    monkeypatch.delenv("SME_LLM", raising=False)
    body = make_client(db_session, []).get("/config/domain").json()
    assert set(body) == {"domain", "kpis", "machines", "shifts", "sops", "llm"}
    assert body["domain"] == CFG.domain
    assert body["kpis"] == [{"name": k.name, "unit": k.unit, "direction": k.direction} for k in CFG.kpis]
    assert body["machines"] == CFG.plant.machines and body["shifts"] == CFG.plant.shifts
    assert body["sops"]
    assert all(set(s) == {"sop_id", "version"} for s in body["sops"])
    assert {s["sop_id"] for s in body["sops"]} == {s.id for s in CFG.sop}
    assert body["llm"] == "real"


def test_llm_scripted_follows_env(db_session, monkeypatch):
    monkeypatch.setenv("SME_LLM", "scripted")
    assert make_client(db_session, []).get("/config/domain").json()["llm"] == "scripted"
    monkeypatch.setenv("SME_LLM", "")
    assert make_client(db_session, []).get("/config/domain").json()["llm"] == "real"


def test_sop_version_rises_after_approved_apply(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])

    def version():
        return {s["sop_id"]: s["version"] for s in client.get("/config/domain").json()["sops"]}[SOP_ID]

    v0 = version()
    run = start(client)
    assert approve(client, run["run_id"], HUMAN).status_code == 200
    assert version() == v0 + 1
    assert version() == v0 + 1  # repeated call: same answer


def test_no_model_name_and_no_writes(db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL_SONNET", "claude-secret-model")
    client = make_client(db_session, [])
    before = total_rows(db_session)
    for _ in range(2):
        r = client.get("/config/domain")
        assert r.status_code == 200 and "claude-" not in r.text
        assert "claude-" not in json.dumps(r.json())
    assert total_rows(db_session) == before
    for method in (client.post, client.put, client.delete):
        assert method("/config/domain").status_code in (404, 405)
