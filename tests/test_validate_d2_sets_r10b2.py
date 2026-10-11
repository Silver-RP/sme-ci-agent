"""R10b2/dev-07: validator against EVERY set in data/templates/invalid/ (D2, #126/#128).

Expected answers are copied from data/templates/README.md, section 4 (source: README, not the validator).
Tuple = (code, severity, table, row, column, value); None = "—" (empty); "*" = contract does not fix it (not compared).
A directory without an answer here fails the test, so adding a set forces adding its answer.
"""

from pathlib import Path

import pytest

from backend.sandbox.validate import validate_directory

ROOT = Path(__file__).resolve().parents[1]
INVALID = ROOT / "data" / "templates" / "invalid"
VALID = ROOT / "data" / "templates" / "valid"

E, W, N = "error", "warning", "note"
BASE = ("V08", W, "production_log", None, "shift_start", "1")  # "nền" in README section 3


def _v(code, sev, table, row, col, val):
    return (code, sev, table, row, col, val)


D2_ANSWERS = {
    "V01a_missing_file": [_v("V01", E, "sop", None, None, "sop.csv"), BASE],
    "V01b_empty_file": [_v("V01", E, "sop", None, None, "*"), BASE],
    "V01c_header_only": [_v("V01", E, "sop", None, None, "*"), BASE],
    "V01d_missing_column": [
        _v("V01", E, "production_log", None, "units_nonconforming", "*"),
        _v("N04", N, "production_log", None, "units_nonconforming", "defect_rate"),
        BASE,
    ],
    "V01d_wrong_case": [
        _v("V01", E, "production_log", None, "shift_start", "*"),
        _v("N02", W, "production_log", None, "Shift_Start", "*"),
    ],
    "V01d_missing_conditional_column": [_v("V01", E, "machine_log", None, "parameter", "*"), BASE],
    "V01e_duplicate_column": [_v("V01", E, "production_log", None, "product_id", "*"), BASE],
    "V02_int_decimal": [_v("V02", E, "production_log", 9, "units_produced", "820.0"), BASE],
    "V02_conditional_empty": [_v("V02", E, "machine_log", 4, "parameter", ""), BASE],
    "V02_row_cell_count": [_v("V02", E, "production_log", 9, None, "*"), BASE],
    "V02_bool": [_v("V02", E, "shift_schedule", 9, "is_substitute", "TRUE"), BASE],
    "V02_date": [_v("V02", E, "shift_schedule", 2, "date", "2026-02-30"), BASE],
    "V02_float_comma": [_v("V02", E, "machine_log", 4, "old_value", "180,5"), BASE],
    "V03_nonconforming_gt_produced": [_v("V03", E, "production_log", 9, "units_nonconforming", "830"), BASE],
    "V03_reworked_gt_produced": [_v("V03", E, "production_log", 9, "units_reworked", "900"), BASE],
    "V03_negative_count": [_v("V03", E, "production_log", 9, "units_reworked", "-1"), BASE],
    "V03_shift_start_hour": [_v("V03", E, "production_log", 9, "shift_start", "2026-03-10T21:00:00"), BASE],
    "V03_setpoint_out_of_limits": [_v("V03", E, "machine_log", 4, "new_value", "250"), BASE],
    "V03_expiry_before_received": [_v("V03", E, "material_batches", 2, "expiry_date", "2026-02-02"), BASE],
    "V03_qc_result_invalid": [_v("V03", E, "material_batches", 2, "qc_result", "ok"), BASE],
    "V03_sop_version_lt_1": [
        _v("V03", E, "sop", 6, "version", "0"),
        _v("V03", E, "sop", 6, "step_no", "1"),
        BASE,
    ],
    "V03_sop_step_no_lt_1": [
        _v("V03", E, "sop", 3, "step_no", "0"),
        _v("V03", E, "sop", 2, "step_no", "2"),
        BASE,
    ],
    "V03_sop_step_gap": [_v("V03", E, "sop", 2, "step_no", "3"), BASE],
    "V03_sop_title_mismatch": [_v("V03", E, "sop", 3, "title", "Reflow setpoint check rev B"), BASE],
    "V04_duplicate_key": [_v("V04", E, "shift_schedule", 11, "date", "9"), BASE],
    "V05_event_type": [_v("V05", E, "machine_log", 6, "event_type", "recipe_swap"), BASE],
    "V05_parameter": [_v("V05", E, "machine_log", 7, "parameter", "zone9_temp_c"), BASE],
    "V05_machine_case": [_v("V05", E, "production_log", 9, "machine_id", "m02"), BASE],
    "V06_gap": [
        _v("V06", W, "production_log", None, "machine_id", "M02 2026-03-11T06:00:00/2026-03-12T06:00:00 (4)"),
        _v("V08", W, "production_log", None, "shift_start", "3"),
    ],
    "V07a_operator": [_v("V07", W, "machine_log", 4, "operator_id", "OP-099"), BASE],
    "V07b_batch": [_v("V07", W, "production_log", 9, "batch_id", "PST-9999-99"), BASE],
    "V08_short_history": [_v("V08", W, "production_log", None, "shift_start", "41")],
    "V09a_header": [
        _v("V09", E, "shift_schedule", None, "operator_name", "*"),
        _v("N02", W, "shift_schedule", None, "operator_name", "*"),
        BASE,
    ],
    "V09a_header_camelcase": [
        _v("V09", E, "shift_schedule", None, "OperatorName", "*"),
        _v("N02", W, "shift_schedule", None, "OperatorName", "*"),
        BASE,
    ],
    "V09b_operator_value": [_v("V09", E, "shift_schedule", 3, "operator_id", "Nguyen Van A"), BASE],
    "N01_extra_file": [_v("N01", W, "kpi_log.csv", None, "*", "*"), BASE],
    "N03_zero_produced": [_v("N03", N, "production_log", 9, "*", "*"), BASE],
}


def _key(i):
    return (i["code"], i["severity"], i["table"], i["row"], i["column"], i["value"])


def _match(got, expected):
    return all(e == "*" or g == e for g, e in zip(got, expected, strict=True))


def _assert_same_set(issues, expected):
    got = [_key(i) for i in issues]
    assert len(got) == len(expected), got
    left = list(got)
    for e in expected:
        hit = next((g for g in left if _match(g, e)), None)
        assert hit is not None, (e, got)
        left.remove(hit)


def _dirs():
    return sorted(p.name for p in INVALID.iterdir() if p.is_dir())


def test_d2_has_37_sets_and_each_has_an_answer():
    assert len(_dirs()) == 37
    assert set(_dirs()) == set(D2_ANSWERS)


@pytest.mark.parametrize("name", _dirs())
def test_every_invalid_set_matches_readme_answer(name):
    assert name in D2_ANSWERS, f"no README answer in test for new set {name}"
    _assert_same_set(validate_directory(INVALID / name), D2_ANSWERS[name])


def test_valid_has_only_the_baseline_warning():
    _assert_same_set(validate_directory(VALID), [BASE])
    assert not [i for i in validate_directory(VALID) if i["severity"] == "error"]
