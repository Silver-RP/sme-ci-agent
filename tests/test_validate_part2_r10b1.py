"""R10b1/dev-05: input validation part 2 (V03-V08, N03, N04) on top of the part 1 module."""

import shutil
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.sandbox.validate import validate_directory

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "data" / "templates" / "valid"
INVALID = ROOT / "data" / "templates" / "invalid"
CFG = load_domain_config()
SCOPE2 = {"V03", "V04", "V05", "V06", "V07", "V08", "N03", "N04"}
E, W, N = "error", "warning", "note"
BASELINE = ("V08", W, "production_log", None, "shift_start", "1")  # 1 day of data in the template set

PL_HEAD = "shift_start,shift,machine_id,units_produced,units_nonconforming,units_reworked,product_id,batch_id"
SS_HEAD = "date,shift,machine_id,operator_id,is_substitute"


def key(i):
    return (i["code"], i["severity"], i["table"], i["row"], i["column"], i["value"])


def scope2(issues, baseline=False):
    got = [key(i) for i in issues if i["code"] in SCOPE2]
    if not baseline and BASELINE in got:
        got.remove(BASELINE)
    return got


def make_dir(tmp_path, **files):
    d = tmp_path / "data"
    shutil.copytree(VALID, d)
    for name, content in files.items():
        f = d / name
        if content is None:
            f.unlink()
        else:
            f.write_text(content, encoding="utf-8")
    return d


def replace(name, old, new, count=1):
    text = (VALID / name).read_text(encoding="utf-8")
    assert old in text
    return text.replace(old, new, count)


def run(d):
    return validate_directory(d, CFG)


# ---- D2 sets: exactly one V code as named ---------------------------------------------------------------

D2 = {
    "V03_expiry_before_received": [("V03", E, "material_batches", 2, "expiry_date", "2026-02-02")],
    "V03_negative_count": [("V03", E, "production_log", 9, "units_reworked", "-1")],
    "V03_nonconforming_gt_produced": [("V03", E, "production_log", 9, "units_nonconforming", "830")],
    "V03_qc_result_invalid": [("V03", E, "material_batches", 2, "qc_result", "ok")],
    "V03_reworked_gt_produced": [("V03", E, "production_log", 9, "units_reworked", "900")],
    "V03_setpoint_out_of_limits": [("V03", E, "machine_log", 4, "new_value", "250")],
    "V03_shift_start_hour": [("V03", E, "production_log", 9, "shift_start", "2026-03-10T21:00:00")],
    "V03_sop_step_gap": [("V03", E, "sop", 2, "step_no", "3")],
    "V03_sop_step_no_lt_1": [("V03", E, "sop", 3, "step_no", "0"), ("V03", E, "sop", 2, "step_no", "2")],
    "V03_sop_title_mismatch": [("V03", E, "sop", 3, "title", "Reflow setpoint check rev B")],
    "V03_sop_version_lt_1": [("V03", E, "sop", 6, "version", "0"), ("V03", E, "sop", 6, "step_no", "1")],
    "V04_duplicate_key": [("V04", E, "shift_schedule", 11, "date", "9")],
    "V05_event_type": [("V05", E, "machine_log", 6, "event_type", "recipe_swap")],
    "V05_machine_case": [("V05", E, "production_log", 9, "machine_id", "m02")],
    "V05_parameter": [("V05", E, "machine_log", 7, "parameter", "zone9_temp_c")],
    "V06_gap": [
        ("V06", W, "production_log", None, "machine_id", "M02 2026-03-11T06:00:00/2026-03-12T06:00:00 (4)"),
        ("V08", W, "production_log", None, "shift_start", "3"),
    ],
    "V07a_operator": [("V07", W, "machine_log", 4, "operator_id", "OP-099")],
    "V07b_batch": [("V07", W, "production_log", 9, "batch_id", "PST-9999-99")],
    "V08_short_history": [("V08", W, "production_log", None, "shift_start", "41")],
}
PART2_PREFIX = ("V03", "V04", "V05", "V06", "V07", "V08")


@pytest.mark.parametrize("name", sorted(D2))
def test_d2_set_gives_exactly_the_named_code(name):
    issues = run(INVALID / name)
    assert sorted(scope2(issues), key=str) == sorted(D2[name], key=str)
    code = name[:3]
    # every V item (not the V08 baseline of the template) has the code of the folder name
    codes = {i["code"] for i in issues if i["code"].startswith("V")}
    assert codes - {"V08"} <= {code}
    assert not [i for i in issues if i["code"] in ("V01", "V02", "V09")]
    assert not [i for i in issues if i["code"].startswith("N0") and i["code"] in ("N03", "N04")]


def test_every_d2_part2_set_is_covered_by_a_test():
    names = {p.name for p in INVALID.iterdir() if p.name[:3] in PART2_PREFIX}
    assert names == set(D2)


def test_valid_templates_only_have_the_v08_baseline():
    assert scope2(run(VALID), baseline=True) == [BASELINE]


# ---- V03 ------------------------------------------------------------------------------------------------


def test_v03_pass_and_violation_counts_and_shift_hour(tmp_path):
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02,820,17,5", "2026-03-10T22:00:00,night,M02,820,830,5")
    assert scope2(run(make_dir(tmp_path, **{"production_log.csv": bad}))) == [
        ("V03", E, "production_log", 9, "units_nonconforming", "830")
    ]
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02", "2026-03-10T21:00:00,night,M02")
    assert scope2(run(make_dir(tmp_path / "b", **{"production_log.csv": bad}))) == [
        ("V03", E, "production_log", 9, "shift_start", "2026-03-10T21:00:00")
    ]


def test_v03_shift_start_minutes_and_seconds_must_be_zero(tmp_path):
    for i, ts in enumerate(("2026-03-10T22:30:00", "2026-03-10T22:00:01")):
        bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02", f"{ts},night,M02")
        got = scope2(run(make_dir(tmp_path / str(i), **{"production_log.csv": bad})))
        assert got == [("V03", E, "production_log", 9, "shift_start", ts)]


def test_v03_two_constraints_on_one_row_give_two_items(tmp_path):
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02,820,17,5", "2026-03-10T22:00:00,night,M02,820,-3,900")
    got = scope2(run(make_dir(tmp_path, **{"production_log.csv": bad})))
    assert sorted(got) == sorted(
        [
            ("V03", E, "production_log", 9, "units_nonconforming", "-3"),
            ("V03", E, "production_log", 9, "units_reworked", "900"),
        ]
    )


def test_v03_negative_produced_and_equal_counts_are_ok(tmp_path):
    ok = replace("production_log.csv", "2026-03-10T22:00:00,night,M02,820,17,5", "2026-03-10T22:00:00,night,M02,820,820,820")
    assert scope2(run(make_dir(tmp_path, **{"production_log.csv": ok}))) == []
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02,820,17,5", "2026-03-10T22:00:00,night,M02,-820,17,5")
    assert ("V03", E, "production_log", 9, "units_produced", "-820") in scope2(
        run(make_dir(tmp_path / "b", **{"production_log.csv": bad}))
    )


def test_v03_setpoint_limits_inclusive_old_equals_new_and_only_setpoint_rows(tmp_path):
    lo, hi = CFG.actions.limits["zone3_setpoint_c"].min, CFG.actions.limits["zone3_setpoint_c"].max
    ok = replace("machine_log.csv", "zone3_setpoint_c,180,195,", f"zone3_setpoint_c,{lo:g},{hi:g},")
    assert scope2(run(make_dir(tmp_path, **{"machine_log.csv": ok}))) == []
    same = replace("machine_log.csv", "zone3_setpoint_c,180,195,", "zone3_setpoint_c,195,195,")
    assert scope2(run(make_dir(tmp_path / "s", **{"machine_log.csv": same}))) == []
    bad = replace("machine_log.csv", "zone3_setpoint_c,180,195,", f"zone3_setpoint_c,{lo - 1:g},{hi + 1:g},")
    got = scope2(run(make_dir(tmp_path / "b", **{"machine_log.csv": bad})))
    assert sorted(got) == sorted(
        [
            ("V03", E, "machine_log", 4, "old_value", f"{lo - 1:g}"),
            ("V03", E, "machine_log", 4, "new_value", f"{hi + 1:g}"),
        ]
    )
    # alarm: new_value out of limits is not checked (format only)
    alarm = replace("machine_log.csv", "zone3_setpoint_c,,188.4,", "zone3_setpoint_c,,999.9,")
    assert scope2(run(make_dir(tmp_path / "a", **{"machine_log.csv": alarm}))) == []


def test_v03_unknown_parameter_has_no_limit_check(tmp_path):
    bad = replace("machine_log.csv", "zone3_setpoint_c,180,195,", "zone9_temp_c,0,9999,")
    got = scope2(run(make_dir(tmp_path, **{"machine_log.csv": bad})))
    assert got == [("V05", E, "machine_log", 4, "parameter", "zone9_temp_c")]


def test_v03_material_expiry_equal_ok_and_qc_values(tmp_path):
    ok = replace("material_batches.csv", "2026-03-02,2026-09-02,pass", "2026-03-02,2026-03-02,fail")
    assert scope2(run(make_dir(tmp_path, **{"material_batches.csv": ok}))) == []
    bad = replace("material_batches.csv", "2026-03-02,2026-09-02,pass", "2026-03-02,2026-03-01,PASS")
    got = scope2(run(make_dir(tmp_path / "b", **{"material_batches.csv": bad})))
    assert sorted(got) == sorted(
        [
            ("V03", E, "material_batches", 2, "expiry_date", "2026-03-01"),
            ("V03", E, "material_batches", 2, "qc_result", "PASS"),
        ]
    )


def test_v03_sop_example_gap_and_missing_numbers_listed(tmp_path):
    sop = replace("sop.csv", "check,3,Run a first-article inspection", "check,4,Run a first-article inspection")
    assert scope2(run(make_dir(tmp_path, **{"sop.csv": sop}))) == [("V03", E, "sop", 2, "step_no", "3")]
    sop = replace("sop.csv", "check,3,Run a first-article inspection", "check,6,Run a first-article inspection")
    got = scope2(run(make_dir(tmp_path / "m", **{"sop.csv": sop})))
    assert got == [("V03", E, "sop", 2, "step_no", "3, 4, 5")]


def test_v03_sop_steps_are_a_set_independent_of_row_order(tmp_path):
    lines = (VALID / "sop.csv").read_text(encoding="utf-8").splitlines()
    shuffled = "\n".join([lines[0], lines[3], lines[1], lines[2], *lines[4:]]) + "\n"
    assert scope2(run(make_dir(tmp_path, **{"sop.csv": shuffled}))) == []


def test_v03_sop_title_reported_on_each_row_that_differs_from_first(tmp_path):
    sop = replace("sop.csv", "check,2,Record", "check X,2,Record")
    sop = sop.replace("check,3,Run", "check Y,3,Run")
    got = scope2(run(make_dir(tmp_path, **{"sop.csv": sop})))
    assert sorted(got) == sorted(
        [
            ("V03", E, "sop", 3, "title", "Reflow setpoint check X"),
            ("V03", E, "sop", 4, "title", "Reflow setpoint check Y"),
        ]
    )


def test_v03_skips_cells_already_rejected_by_v02(tmp_path):
    # units_produced "820.0" is V02; the nonconforming comparison must not produce V03
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02,820,17,5", "2026-03-10T22:00:00,night,M02,820.0,900,5")
    issues = run(make_dir(tmp_path, **{"production_log.csv": bad}))
    assert [key(i) for i in issues if i["code"] == "V02"] == [("V02", E, "production_log", 9, "units_produced", "820.0")]
    assert scope2(issues) == []
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02", "2026-03-10 21:00:00,night,M02")
    assert scope2(run(make_dir(tmp_path / "t", **{"production_log.csv": bad}))) == []


def test_v03_shift_outside_config_has_no_hour_check(tmp_path):
    bad = replace("production_log.csv", "2026-03-10T22:00:00,night,M02", "2026-03-10T21:00:00,dusk,M02")
    got = scope2(run(make_dir(tmp_path, **{"production_log.csv": bad})))
    assert ("V05", E, "production_log", 9, "shift", "dusk") in got
    assert not [g for g in got if g[0] == "V03"]


# ---- V04 ------------------------------------------------------------------------------------------------


def test_v04_example_and_three_duplicates_give_two_items(tmp_path):
    dup = (VALID / "shift_schedule.csv").read_text(encoding="utf-8") + "2026-03-10,night,M02,OP-021,false\n"
    assert scope2(run(make_dir(tmp_path, **{"shift_schedule.csv": dup}))) == [("V04", E, "shift_schedule", 11, "date", "9")]
    dup += "2026-03-10,night,M02,OP-022,false\n"
    got = scope2(run(make_dir(tmp_path / "t", **{"shift_schedule.csv": dup})))
    assert sorted(got) == sorted(
        [("V04", E, "shift_schedule", 11, "date", "9"), ("V04", E, "shift_schedule", 12, "date", "9")]
    )


def test_v04_same_operator_two_machines_is_valid(tmp_path):
    ok = replace("shift_schedule.csv", "2026-03-10,morning,M02,OP-005", "2026-03-10,morning,M02,OP-003")
    assert scope2(run(make_dir(tmp_path, **{"shift_schedule.csv": ok}))) == []


def test_v04_keys_of_other_tables_and_parsed_values(tmp_path):
    pl = (VALID / "production_log.csv").read_text(encoding="utf-8") + "2026-03-10T22:00:00,night,M02,1,0,0,,\n"
    mb = (VALID / "material_batches.csv").read_text(encoding="utf-8") + "PST-2603-01,X,SUP-01,2026-03-01,,\n"
    sop = (VALID / "sop.csv").read_text(encoding="utf-8") + "SOP-CAL-002,01,Machine calibration routine,02,Dup by value\n"
    got = scope2(run(make_dir(tmp_path, **{"production_log.csv": pl, "material_batches.csv": mb, "sop.csv": sop})))
    assert sorted(got) == sorted(
        [
            ("V04", E, "production_log", 11, "shift_start", "9"),
            ("V04", E, "material_batches", 7, "batch_id", "2"),
            ("V04", E, "sop", 7, "sop_id", "6"),
        ]
    )


def test_v04_row_with_v02_key_cell_does_not_take_part(tmp_path):
    ss = (VALID / "shift_schedule.csv").read_text(encoding="utf-8") + "2026-03-10,night,M02,OP-021,TRUE\n2026-3-10,night,M02,OP-021,false\n"
    issues = run(make_dir(tmp_path, **{"shift_schedule.csv": ss}))
    assert next(i for i in issues if i["code"] == "V04")["row"] == 11
    assert len([i for i in issues if i["code"] == "V04"]) == 1  # the row with date 2026-3-10 is V02, not V04


def test_v04_machine_log_has_no_key(tmp_path):
    ml = (VALID / "machine_log.csv").read_text(encoding="utf-8")
    ml += ml.splitlines()[3] + "\n"
    assert scope2(run(make_dir(tmp_path, **{"machine_log.csv": ml}))) == []


# ---- V05 ------------------------------------------------------------------------------------------------


def test_v05_examples(tmp_path):
    ml = replace("machine_log.csv", "M02,program_change", "M02,recipe_swap")
    assert scope2(run(make_dir(tmp_path, **{"machine_log.csv": ml}))) == [("V05", E, "machine_log", 6, "event_type", "recipe_swap")]
    ml = replace("machine_log.csv", "alarm,zone3_setpoint_c", "alarm,zone9_temp_c")
    assert scope2(run(make_dir(tmp_path / "p", **{"machine_log.csv": ml}))) == [
        ("V05", E, "machine_log", 7, "parameter", "zone9_temp_c")
    ]


def test_v05_machine_and_shift_codes_in_each_table(tmp_path):
    pl = replace("production_log.csv", "night,M02", "Night,M02")
    ss = replace("shift_schedule.csv", "night,M03", "night,M04")
    ml = replace("machine_log.csv", "M03,calibration", "m03,calibration")
    got = scope2(run(make_dir(tmp_path, **{"production_log.csv": pl, "shift_schedule.csv": ss, "machine_log.csv": ml})))
    assert sorted(got) == sorted(
        [
            ("V05", E, "production_log", 9, "shift", "Night"),
            ("V05", E, "shift_schedule", 10, "machine_id", "M04"),
            ("V05", E, "machine_log", 2, "machine_id", "m03"),
        ]
    )


def test_v05_parameter_ignored_for_other_event_types_and_empty_alarm_parameter_ok(tmp_path):
    ml = replace("machine_log.csv", "calibration,,,", "calibration,zone9_temp_c,abc,xyz")
    ml = ml.replace("alarm,zone3_setpoint_c,,188.4", "alarm,,,")
    assert scope2(run(make_dir(tmp_path, **{"machine_log.csv": ml}))) == []


def test_v05_unknown_event_type_means_parameter_is_ignored(tmp_path):
    ml = replace("machine_log.csv", "M03,calibration,,,", "M03,recipe_swap,zone9_temp_c,,")
    assert scope2(run(make_dir(tmp_path, **{"machine_log.csv": ml}))) == [("V05", E, "machine_log", 2, "event_type", "recipe_swap")]


# ---- V06 ------------------------------------------------------------------------------------------------


def _long_history(path: Path, gaps: set[tuple[date, str]], days: int = 50, machine: str = "M02") -> None:
    """production_log of ``days`` days for M01-M03 (valid hours); ``machine`` lacks the (date, shift) cells in ``gaps``."""
    start = date(2026, 1, 1)
    lines = [PL_HEAD]
    ss = [SS_HEAD]
    for k in range(days):
        day = start + timedelta(days=k)
        for shift, hour in CFG.plant.shift_start_hours.items():
            for m in CFG.plant.machines:
                if m == machine and (day, shift) in gaps:
                    continue
                lines.append(f"{day.isoformat()}T{hour:02d}:00:00,{shift},{m},100,2,1,PCB-A,")
                ss.append(f"{day.isoformat()},{shift},{m},OP-003,false")
    (path / "production_log.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (path / "shift_schedule.csv").write_text("\n".join(ss) + "\n", encoding="utf-8")


def test_v06_boundary_three_cells_ok_five_cells_warn(tmp_path):
    shifts = CFG.plant.shifts
    sunday = date(2026, 1, 11)
    three = {(sunday, s) for s in shifts}
    d = make_dir(tmp_path)
    _long_history(d, three)
    assert [g for g in scope2(run(d), baseline=True) if g[0] in ("V06", "V08")] == []
    five = {(sunday, s) for s in shifts} | {(sunday + timedelta(days=1), s) for s in shifts[:2]}
    _long_history(d, five)
    got = [g for g in scope2(run(d)) if g[0] == "V06"]
    assert got == [("V06", W, "production_log", None, "machine_id", "M02 2026-01-11T06:00:00/2026-01-12T14:00:00 (5)")]


def test_v06_gap_at_start_of_range_counts_and_only_machines_with_data(tmp_path):
    d = make_dir(tmp_path)
    # M02 has nothing during the first 2 days (6 cells) but exists later; M09 never appears
    gaps = {(date(2026, 1, 1), s) for s in CFG.plant.shifts} | {(date(2026, 1, 2), s) for s in CFG.plant.shifts}
    _long_history(d, gaps)
    got = [g for g in scope2(run(d)) if g[0] == "V06"]
    assert got == [("V06", W, "production_log", None, "machine_id", "M02 2026-01-01T06:00:00/2026-01-02T22:00:00 (6)")]


def test_v06_zero_units_row_counts_as_present_and_two_gaps_two_items(tmp_path):
    d = make_dir(tmp_path)
    g1 = {(date(2026, 1, 5), s) for s in CFG.plant.shifts} | {(date(2026, 1, 6), "morning")}
    g2 = {(date(2026, 1, 20), s) for s in CFG.plant.shifts} | {(date(2026, 1, 21), "morning")}
    _long_history(d, g1 | g2)
    got = [g for g in scope2(run(d)) if g[0] == "V06"]
    assert sorted(g[5] for g in got) == [
        "M02 2026-01-05T06:00:00/2026-01-06T06:00:00 (4)",
        "M02 2026-01-20T06:00:00/2026-01-21T06:00:00 (4)",
    ]
    # a row with units_produced = 0 fills its cell (and gives N03)
    path = d / "production_log.csv"
    path.write_text(path.read_text() + "2026-01-05T22:00:00,night,M02,0,0,0,PCB-A,\n", encoding="utf-8")
    issues = run(d)
    # the filled cell splits the first gap into runs of 2 and 1 cells, both below the limit
    assert [g[5] for g in scope2(issues) if g[0] == "V06"] == ["M02 2026-01-20T06:00:00/2026-01-21T06:00:00 (4)"]
    assert len([i for i in issues if i["code"] == "V06"]) == 1


def test_v06_rows_with_bad_shift_start_or_unknown_shift_do_not_take_part(tmp_path):
    d = make_dir(tmp_path)
    _long_history(d, set())
    path = d / "production_log.csv"
    # a row with shift_start broken (V02) and one with unknown shift would otherwise stretch the range
    path.write_text(path.read_text() + "2030-01-01 06:00,morning,M01,1,0,0,,\n2031-01-01T06:00:00,dusk,M01,1,0,0,,\n", encoding="utf-8")
    assert [g for g in scope2(run(d)) if g[0] == "V06"] == []


# ---- V07 ------------------------------------------------------------------------------------------------


def test_v07_each_unknown_value_once_at_first_row(tmp_path):
    ml = replace("machine_log.csv", "OP-008", "OP-099")
    ml = ml.replace("OP-011", "OP-099").replace("OP-021", "OP-098")
    got = scope2(run(make_dir(tmp_path, **{"machine_log.csv": ml})))
    assert sorted(got) == sorted(
        [("V07", W, "machine_log", 2, "operator_id", "OP-099"), ("V07", W, "machine_log", 5, "operator_id", "OP-098")]
    )


def test_v07_operator_does_not_need_same_day_or_machine_and_empty_is_ok(tmp_path):
    ml = replace("machine_log.csv", "M03,calibration,,,,OP-008", "M01,calibration,,,,OP-017")
    assert scope2(run(make_dir(tmp_path, **{"machine_log.csv": ml}))) == []
    ml = replace("machine_log.csv", "M03,calibration,,,,OP-008", "M03,calibration,,,,")
    assert scope2(run(make_dir(tmp_path / "e", **{"machine_log.csv": ml}))) == []


def test_v07_batch_missing_file_flags_every_distinct_batch(tmp_path):
    got = scope2(run(make_dir(tmp_path, **{"material_batches.csv": None})))
    assert sorted(g[5] for g in got if g[0] == "V07") == ["PST-2603-01", "PST-2603-02"]
    assert {g[3] for g in got if g[0] == "V07"} == {2, 4}


def test_v07_header_only_material_batches_flags_batches_and_empty_batch_id_is_ok(tmp_path):
    mb = "batch_id,material_id,supplier_id,received_date,expiry_date,qc_result\n"
    got = scope2(run(make_dir(tmp_path, **{"material_batches.csv": mb})))
    assert len([g for g in got if g[0] == "V07"]) == 2
    pl = (VALID / "production_log.csv").read_text(encoding="utf-8").replace("PST-2603-01", "").replace("PST-2603-02", "")
    assert scope2(run(make_dir(tmp_path / "e", **{"production_log.csv": pl}))) == []


def test_v07_operator_cell_rejected_by_v09_is_not_reported(tmp_path):
    ml = replace("machine_log.csv", "OP-008", "op-008")
    issues = run(make_dir(tmp_path, **{"machine_log.csv": ml}))
    assert any(i["code"] == "V09" for i in issues)
    assert scope2(issues) == []


# ---- V08 ------------------------------------------------------------------------------------------------


def _days_dir(tmp_path, days: int, first=date(2026, 1, 1)):
    d = make_dir(tmp_path)
    lines = [PL_HEAD]
    lines.append(f"{first.isoformat()}T06:00:00,morning,M01,100,2,1,PCB-A,")
    last = first + timedelta(days=days - 1)
    lines.append(f"{last.isoformat()}T14:00:00,afternoon,M01,100,2,1,PCB-A,")
    (d / "production_log.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def test_v08_boundary_42_ok_41_warns_with_both_ends_counted(tmp_path):
    ok = [g for g in scope2(run(_days_dir(tmp_path, 42)), baseline=True) if g[0] == "V08"]
    assert ok == []
    got = [g for g in scope2(run(_days_dir(tmp_path / "b", 41))) if g[0] == "V08"]
    assert got == [("V08", W, "production_log", None, "shift_start", "41")]


def test_v08_threshold_comes_from_config(tmp_path):
    cfg = CFG.model_copy(update={"detect": CFG.detect.model_copy(update={"reference_days": 10}),
                                 "validate_": CFG.validate_.model_copy(update={"min_monitor_days": 0})})
    d = _days_dir(tmp_path, 10)
    assert [i for i in validate_directory(d, cfg) if i["code"] == "V08"] == []
    d = _days_dir(tmp_path / "b", 9)
    assert [i["value"] for i in validate_directory(d, cfg) if i["code"] == "V08"] == ["9"]


def test_v08_bad_shift_start_rows_are_ignored(tmp_path):
    d = _days_dir(tmp_path, 42)
    path = d / "production_log.csv"
    path.write_text(path.read_text() + "2020-01-01 06:00,morning,M01,1,0,0,,\n", encoding="utf-8")
    assert [i for i in run(d) if i["code"] == "V08"] == []


# ---- N03, N04 -------------------------------------------------------------------------------------------


def test_n03_zero_units_row_in_file_order_and_blank_lines(tmp_path):
    pl = (VALID / "production_log.csv").read_text(encoding="utf-8")
    pl = pl.replace("2026-03-10T06:00:00,morning,M02,810,16,5", "2026-03-10T06:00:00,morning,M02,0,0,0")
    pl = pl.replace("2026-03-10T22:00:00,night,M01,700,14,4", "\n2026-03-10T22:00:00,night,M01,0,0,0")
    got = [g for g in scope2(run(make_dir(tmp_path, **{"production_log.csv": pl}))) if g[0] == "N03"]
    assert sorted(got) == sorted(
        [("N03", N, "production_log", 3, "units_produced", "0"), ("N03", N, "production_log", 9, "units_produced", "0")]
    )


def test_n03_is_one_item_per_row_not_per_kpi_and_no_v_code(tmp_path):
    assert len(CFG.kpis) >= 2
    pl = (VALID / "production_log.csv").read_text(encoding="utf-8").replace("810,16,5", "0,0,0")
    issues = run(make_dir(tmp_path, **{"production_log.csv": pl}))
    assert len([i for i in issues if i["code"] == "N03"]) == 1
    assert scope2(issues) == [("N03", N, "production_log", 3, "units_produced", "0")]


def test_n04_missing_optional_numerator_column(tmp_path):
    kpi = next(k for k in CFG.kpis if k.numerator == "units_reworked")
    pl = "\n".join(",".join(c for i, c in enumerate(line.split(",")) if i != 5) for line in (VALID / "production_log.csv").read_text(encoding="utf-8").splitlines()) + "\n"
    got = scope2(run(make_dir(tmp_path, **{"production_log.csv": pl})))
    assert got == [("N04", N, "production_log", None, "units_reworked", kpi.name)]


def test_n03_n04_not_reported_when_table_is_unusable(tmp_path):
    got = scope2(run(make_dir(tmp_path, **{"production_log.csv": PL_HEAD + "\n"})))
    assert not [g for g in got if g[0] in ("N03", "N04")]


def test_n03_ignores_zero_when_cell_is_not_a_clean_number(tmp_path):
    pl = (VALID / "production_log.csv").read_text(encoding="utf-8").replace("810,16,5", "0.0,16,5")
    issues = run(make_dir(tmp_path, **{"production_log.csv": pl}))
    assert [i["code"] for i in issues if i["code"] in ("V02", "N03")] == ["V02"]


# ---- simulator, repeatability, structure ----------------------------------------------------------------


def _write_dataset(ds, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in ("production_log", "machine_log", "shift_schedule", "material_batches", "sop"):
        df = ds.tables[name].copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                fmt = "%Y-%m-%d" if col in ("date", "received_date", "expiry_date") else "%Y-%m-%dT%H:%M:%S"
                df[col] = df[col].dt.strftime(fmt)
            elif df[col].dtype == bool:
                df[col] = df[col].map({True: "true", False: "false"})
        df.to_csv(out / f"{name}.csv", index=False)


def test_simulator_seed_42_has_no_errors(tmp_path):
    _write_dataset(generate_dataset(seed=42), tmp_path / "sim")
    issues = run(tmp_path / "sim")
    assert [key(i) for i in issues if i["severity"] == "error"] == []
    assert [key(i) for i in issues if i["severity"] == "warning"] == []  # none today; list them in the report if this changes


def test_repeated_calls_do_not_leak_state(tmp_path):
    d = make_dir(tmp_path)
    first = run(INVALID / "V06_gap")
    run(INVALID / "V04_duplicate_key")
    assert run(INVALID / "V06_gap") == first
    assert run(d) == run(d)


def test_module_still_hardcodes_no_config_names():
    text = (ROOT / "backend/sandbox/validate.py").read_text(encoding="utf-8")
    for name in ("defect_rate", "rework_rate", "zone3_setpoint_c", "M01", "morning", "setpoint_change", "night"):
        assert name not in text
