"""R10b1/dev-01: config keys of the data contract, new tables, derived kpi_log."""

from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from backend.domain_config import DEFAULT_PROFILE_PATH, load_domain_config
from backend.sandbox.kpi_derive import derive_kpi_log
from backend.sandbox.schema import CONTRACT_TABLE_SCHEMAS, DEPRECATED_TABLES, TABLE_SCHEMAS
from backend.sandbox.simulator import params_from_config

CFG = load_domain_config()


def _prod(rows, columns=None):
    cols = columns or [
        "shift_start", "shift", "machine_id", "units_produced", "units_nonconforming", "units_reworked",
    ]
    df = pd.DataFrame(rows, columns=cols)
    df["shift_start"] = pd.to_datetime(df["shift_start"])
    return df


ROWS = [
    ("2026-03-10T06:00:00", "morning", "M01", 1000, 20, 30),
    ("2026-03-10T14:00:00", "afternoon", "M02", 500, 25, 5),
]


def test_defect_and_rework_rate_values():
    out, notes = derive_kpi_log(_prod(ROWS), CFG)
    assert notes == []
    assert list(out.columns) == list(TABLE_SCHEMAS["kpi_log"])
    assert len(out) == 4  # 2 KPIs x 2 rows
    got = {(r.machine_id, r.kpi): r.value for r in out.itertuples()}
    assert got[("M01", "defect_rate")] == pytest.approx(0.02)
    assert got[("M01", "rework_rate")] == pytest.approx(0.03)
    assert got[("M02", "defect_rate")] == pytest.approx(0.05)
    assert got[("M02", "rework_rate")] == pytest.approx(0.01)
    first = out.iloc[0]
    assert first.timestamp == pd.Timestamp("2026-03-10T06:00:00")
    assert first.date == pd.Timestamp("2026-03-10")
    assert first["shift"] == "morning"


def test_zero_units_produced_no_row_and_note_n03():
    rows = [*ROWS, ("2026-03-10T22:00:00", "night", "M01", 0, 0, 0)]
    out, notes = derive_kpi_log(_prod(rows), CFG)
    assert len(out) == 4
    assert (out.timestamp != pd.Timestamp("2026-03-10T22:00:00")).all()
    n03 = [n for n in notes if n["code"] == "N03"]
    assert len(n03) == 1
    assert n03[0]["severity"] == "note" and n03[0]["table"] == "production_log"
    assert n03[0]["row"] == 4  # header is row 1, third data row is row 4


def test_missing_numerator_column_note_n04():
    df = _prod(ROWS).drop(columns=["units_reworked"])
    out, notes = derive_kpi_log(df, CFG)
    assert set(out["kpi"]) == {"defect_rate"}
    n04 = [n for n in notes if n["code"] == "N04"]
    assert len(n04) == 1
    assert n04[0]["column"] == "units_reworked" and n04[0]["value"] == "rework_rate"
    assert n04[0]["severity"] == "note" and n04[0]["table"] == "production_log"


def test_empty_input_and_repeat_calls_do_not_leak():
    empty = _prod([])
    out, notes = derive_kpi_log(empty, CFG)
    assert out.empty and notes == []
    assert list(out.columns) == list(TABLE_SCHEMAS["kpi_log"])
    df = _prod(ROWS)
    a, na = derive_kpi_log(df, CFG)
    b, nb = derive_kpi_log(df, CFG)
    pd.testing.assert_frame_equal(a, b)
    assert na == nb == []
    assert list(df.columns)[-1] == "units_reworked"  # input untouched


def _cfg_from(tmp_path, mutate):
    data = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_domain_config(p)


def test_kpi_names_and_columns_come_from_config(tmp_path):
    def mutate(d):
        d["kpis"][0]["name"] = "scrap_ratio"
        d["kpis"][0]["numerator"] = "units_reworked"
        d["kpis"][1]["denominator"] = "units_nonconforming"

    cfg = _cfg_from(tmp_path, mutate)
    out, _ = derive_kpi_log(_prod(ROWS), cfg)
    assert set(out["kpi"]) == {"scrap_ratio", "rework_rate"}
    scrap = out[(out.kpi == "scrap_ratio") & (out.machine_id == "M01")].value.iloc[0]
    assert scrap == pytest.approx(0.03)
    rw = out[(out.kpi == "rework_rate") & (out.machine_id == "M02")].value.iloc[0]
    assert rw == pytest.approx(5 / 25)


def test_derive_module_hardcodes_no_names():
    text = (Path(__file__).resolve().parents[1] / "backend/sandbox/kpi_derive.py").read_text(encoding="utf-8")
    for name in ("defect_rate", "rework_rate", "units_nonconforming", "units_reworked", "units_produced"):
        assert name not in text


def test_missing_plant_machines_is_clear_error(tmp_path):
    data = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    del data["plant"]["machines"]
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValidationError, match="machines"):
        load_domain_config(p)


@pytest.mark.parametrize("key", ["shifts", "shift_start_hours"])
def test_missing_other_required_plant_keys(tmp_path, key):
    data = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    del data["plant"][key]
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValidationError, match=key):
        load_domain_config(p)


def test_missing_plant_or_numerator_fails(tmp_path):
    data = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    del data["kpis"][0]["numerator"]
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValidationError, match="numerator"):
        load_domain_config(p)


def test_defaults_match_contract_table(tmp_path):
    def mutate(d):
        for k in ("machine_log", "validate"):
            d.pop(k, None)
        d["plant"].pop("timezone", None)
        for k in d["kpis"]:
            k.pop("denominator", None)

    cfg = _cfg_from(tmp_path, mutate)
    assert cfg.plant.timezone == "Asia/Ho_Chi_Minh"
    assert cfg.machine_log.event_types == [
        "setpoint_change", "program_change", "maintenance", "calibration", "breakdown", "alarm", "note",
    ]
    assert all(k.denominator == "units_produced" for k in cfg.kpis)
    v = cfg.validate_
    assert v.max_missing_shifts == 3 and v.min_monitor_days == 14
    assert v.operator_id_pattern == "^OP-[A-Z0-9]+$"
    assert v.pii_tokens == [
        "name", "fullname", "email", "phone", "tel", "mobile", "address", "birth", "birthday", "dob",
        "cccd", "cmnd",
    ]


def test_shipped_config_has_all_keys():
    assert CFG.plant.machines == ["M01", "M02", "M03"]
    assert CFG.plant.shifts == ["morning", "afternoon", "night"]
    assert CFG.plant.shift_start_hours == {"morning": 6, "afternoon": 14, "night": 22}
    assert {k.name: k.numerator for k in CFG.kpis} == {
        "defect_rate": "units_nonconforming", "rework_rate": "units_reworked",
    }


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda d: d["plant"]["shift_start_hours"].pop("night"), "shift_start_hours"),
        (lambda d: d["plant"]["shift_start_hours"].update(night=24), "0-23"),
        (lambda d: d["machine_log"].update(event_types=["alarm"]), "setpoint_event"),
        (lambda d: d["validate"].update(max_missing_shifts=0), "max_missing_shifts"),
        (lambda d: d["validate"].update(operator_id_pattern="("), "operator_id_pattern"),
    ],
)
def test_invalid_plant_and_validate_values(tmp_path, mutate, match):
    data = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValidationError, match=match):
        load_domain_config(p)


def test_scenario_reads_plant_from_domain_config():
    scenario = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "data/scenarios/scenario1.yaml").read_text(encoding="utf-8")
    )
    for k in ("machines", "shifts", "shift_start_hours"):
        assert k not in scenario["plant"]  # one place only
    p = params_from_config()
    assert p.machines == tuple(CFG.plant.machines)
    assert p.shifts == tuple(CFG.plant.shifts)
    assert p.shift_start_hours == CFG.plant.shift_start_hours


def test_contract_tables_in_schema():
    assert list(CONTRACT_TABLE_SCHEMAS["production_log"])[:5] == [
        "shift_start", "shift", "machine_id", "units_produced", "units_nonconforming",
    ]
    assert set(CONTRACT_TABLE_SCHEMAS["material_batches"]) == {
        "batch_id", "material_id", "supplier_id", "received_date", "expiry_date", "qc_result",
    }
    assert set(CONTRACT_TABLE_SCHEMAS["sop"]) == {"sop_id", "version", "title", "step_no", "step_text"}
    assert set(DEPRECATED_TABLES) == {"inventory", "supplier"}
    assert set(DEPRECATED_TABLES) <= set(TABLE_SCHEMAS)
