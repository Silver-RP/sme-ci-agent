import importlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_backend_packages_import():
    for name in ["sandbox", "detect", "tools", "agent", "api", "db"]:
        importlib.import_module(f"backend.{name}")


def test_events_schema_is_valid_json():
    schema = json.loads((ROOT / "docs/schema/events.json").read_text(encoding="utf-8"))
    assert "type" in schema["properties"]
    assert "agent" in schema["properties"] and "domain" in schema["properties"]


def test_scenario1_loads_and_has_hidden_ground_truth():
    data = yaml.safe_load((ROOT / "data/scenarios/scenario1.yaml").read_text(encoding="utf-8"))
    assert data["id"] == "scenario1"
    assert all(a["ground_truth"]["hidden"] is True for a in data["injected_anomalies"])


def test_context_profile_loads():
    data = yaml.safe_load((ROOT / "data/context_profile.yaml").read_text(encoding="utf-8"))
    assert data["domain"] == "manufacturing"
