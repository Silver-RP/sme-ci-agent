import pandas as pd
import pandas.api.types as pdt
import pytest

from backend.domain_config import load_domain_config
from backend.sandbox import (
    TABLE_NAMES,
    TABLE_SCHEMAS,
    SetpointChange,
    expected_kpi_value,
    params_from_config,
    simulate,
)

CHECKS = {
    "str": lambda s: pdt.is_string_dtype(s) or pdt.is_object_dtype(s),
    "int": pdt.is_integer_dtype,
    "float": pdt.is_float_dtype,
    "bool": pdt.is_bool_dtype,
    "datetime": pdt.is_datetime64_any_dtype,
}


def test_six_tables_with_fixed_schema():
    tables = simulate(params_from_config())
    assert set(tables) == set(TABLE_NAMES) == {
        "kpi_log", "machine_log", "shift_schedule", "inventory", "supplier", "sop"
    }
    for name, df in tables.items():
        assert list(df.columns) == list(TABLE_SCHEMAS[name])
        for col, kind in TABLE_SCHEMAS[name].items():
            assert CHECKS[kind](df[col]), (name, col, df[col].dtype)


def test_schema_holds_for_empty_tables_and_defaults():
    # no setpoint changes -> machine_log empty but still typed
    tables = simulate(params_from_config())
    assert tables["machine_log"].empty
    for col, kind in TABLE_SCHEMAS["machine_log"].items():
        assert CHECKS[kind](tables["machine_log"][col])
    # zero days -> still 6 tables with schema
    empty = simulate(params_from_config().with_(days=0))
    assert list(empty["kpi_log"].columns) == list(TABLE_SCHEMAS["kpi_log"])
    assert empty["kpi_log"].empty


def test_resolution_and_horizon_from_config():
    p = params_from_config()
    kpi = simulate(p)["kpi_log"]
    assert len(kpi) == p.days * len(p.shifts) * len(p.machines)
    assert 180 <= p.days <= 184  # 6 months
    assert not kpi.duplicated(["date", "shift", "machine_id"]).any()


def test_kpi_name_comes_from_config():
    cfg = load_domain_config()
    kpi = simulate(params_from_config())["kpi_log"]
    assert set(kpi["kpi"]) == {"defect_rate"} <= {k.name for k in cfg.kpis}
    other = simulate(params_from_config().with_(kpi="rework_rate"))["kpi_log"]
    assert set(other["kpi"]) == {"rework_rate"}
    assert not any("defect" in c for t in TABLE_SCHEMAS.values() for c in t)


def test_unknown_kpi_in_scenario_rejected(tmp_path):
    import yaml

    from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

    sc = yaml.safe_load(DEFAULT_SCENARIO_PATH.read_text(encoding="utf-8"))
    sc["baseline"]["kpi"] = "not_a_kpi"
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(sc), encoding="utf-8")
    with pytest.raises(ValueError):
        params_from_config(p)


def test_same_seed_identical_different_seed_differs_and_repeatable():
    a = simulate(params_from_config(seed=7))
    b = simulate(params_from_config(seed=7))
    c = simulate(params_from_config(seed=8))
    for name in TABLE_NAMES:
        pd.testing.assert_frame_equal(a[name], b[name])
    assert not a["kpi_log"]["value"].equals(c["kpi_log"]["value"])
    # repeated call after another seed leaks no state
    d = simulate(params_from_config(seed=7))
    pd.testing.assert_frame_equal(a["kpi_log"], d["kpi_log"])


def _mean(tables, machine, start=None, end=None):
    k = tables["kpi_log"]
    k = k[k["machine_id"] == machine]
    if start is not None:
        k = k[k["timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        k = k[k["timestamp"] < pd.Timestamp(end)]
    return k["value"].mean()


def test_setpoint_shift_raises_then_restore_returns_to_baseline():
    p = params_from_config(seed=1)
    sd, base = p.noise_sd, p.baseline
    changes = (
        SetpointChange("M02", pd.Timestamp("2026-03-10T22:00:00"), 195.0),
        SetpointChange("M02", pd.Timestamp("2026-04-20T06:00:00"), 180.0),
    )
    t = simulate(p.with_(setpoint_changes=changes))
    before = _mean(t, "M02", end="2026-03-10T22:00")
    during = _mean(t, "M02", "2026-03-10T22:00", "2026-04-20T06:00")
    after = _mean(t, "M02", "2026-04-20T06:00")
    assert abs(before - base) <= sd
    assert during >= base + 3 * sd
    assert abs(after - base) <= sd
    # other machines untouched
    assert abs(_mean(t, "M01") - base) <= sd
    # changes are logged with old/new values
    ml = t["machine_log"]
    assert list(ml["old_value"]) == [180.0, 195.0]
    assert list(ml["new_value"]) == [195.0, 180.0]
    assert set(ml["event_type"]) == {"setpoint_change"}


def test_expected_kpi_value_zero_deviation_is_baseline():
    assert expected_kpi_value(180, 180, 0.02, 0.0028) == pytest.approx(0.02)
    assert expected_kpi_value(195, 180, 0.02, 0.0028) == pytest.approx(0.062)
    assert expected_kpi_value(165, 180, 0.02, 0.0028) == pytest.approx(0.062)  # symmetric


def test_sandbox_public_names_are_domain_neutral():
    import ast
    from pathlib import Path

    from backend import sandbox

    assert not [n for n in sandbox.__all__ if "defect" in n.lower()]
    for path in Path(sandbox.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text())
        names = [
            n.name
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.ClassDef)
        ]
        assert not [n for n in names if "defect" in n.lower()], path.name


@pytest.mark.parametrize("noise", [0.0, 0.05, 0.5, 5.0])
def test_rate_column_bounded_with_large_noise(noise):
    p = params_from_config(seed=3).with_(
        noise_sd=noise,
        setpoint_changes=(SetpointChange("M01", pd.Timestamp("2026-01-05"), 400.0),),
    )
    v = simulate(p)["kpi_log"]["value"]
    assert v.min() >= 0.0 and v.max() <= 1.0
    assert not v.isna().any()


def test_shift_schedule_and_sop_from_config():
    p = params_from_config()
    t = simulate(p)
    assert set(t["shift_schedule"]["shift"]) == set(p.shifts)
    assert not t["shift_schedule"]["is_substitute"].any()
    cfg = load_domain_config()
    assert set(t["sop"]["sop_id"]) == {s.id for s in cfg.sop}
    assert len(t["sop"]) == sum(len(s.steps) for s in cfg.sop)


def test_empty_machines_gives_empty_kpi_log():
    t = simulate(params_from_config().with_(machines=()))
    assert t["kpi_log"].empty and list(t["kpi_log"].columns) == list(TABLE_SCHEMAS["kpi_log"])
