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


@pytest.mark.parametrize("field", ["domain", "kpis", "hypothesis_groups", "sop"])
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
