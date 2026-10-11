"""R10d/dev-04 (H-49): POST /answer requires question_id. Missing -> 422 naming the field; wrong -> 409; right -> 200."""

import re
from pathlib import Path

from tests.test_answer_question_id_h20 import _waiting_run
from tests.test_api import sse_events

ROOT = Path(__file__).resolve().parents[1]


def test_missing_question_id_is_422_and_nothing_is_answered(db_session):
    client, rid, pending = _waiting_run(db_session)
    n = sum(1 for e in sse_events(client, rid) if e["event"] == "answer_received")
    r = client.post(f"/runs/{rid}/answer", json={"answer": "wait"})
    assert r.status_code == 422 and "question_id" in r.text
    assert client.get(f"/runs/{rid}").json()["pending"]["question_id"] == pending["question_id"]
    assert sum(1 for e in sse_events(client, rid) if e["event"] == "answer_received") == n
    assert client.post(f"/runs/{rid}/answer", json={"answer": "wait", "question_id": ""}).status_code == 422
    assert client.post(f"/runs/{rid}/answer", json={"answer": "wait", "question_id": None}).status_code == 422


def test_wrong_is_409_right_is_200(db_session):
    client, rid, pending = _waiting_run(db_session)
    assert client.post(f"/runs/{rid}/answer", json={"answer": "w", "question_id": "q_stale"}).status_code == 409
    ok = client.post(f"/runs/{rid}/answer", json={"answer": "w", "question_id": pending["question_id"]})
    assert ok.status_code == 200


def test_every_answer_call_in_scripts_and_tests_sends_question_id():
    """Scan: each line that POSTs to /answer in scripts/ and tests/ names question_id in the same line."""
    bad = []
    for path in [*(ROOT / "scripts").glob("*.py"), *(ROOT / "tests").glob("*.py")]:
        if path.name == Path(__file__).name:
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"/answer[\"']", line) and "json=" in line and "question_id" not in line and "# negative" not in line:
                bad.append(f"{path.name}:{n}: {line.strip()}")
    assert not bad, bad
