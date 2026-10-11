"""R10b1/dev-04: input validation part 1 (general rules 4.0, V01, V02, V09, N01, N02)."""

import shutil
from pathlib import Path

import pytest

from backend.domain_config import load_domain_config
from backend.sandbox.validate import parse_table, validate_directory

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "templates"
VALID = TEMPLATES / "valid"
INVALID = TEMPLATES / "invalid"
CFG = load_domain_config()
SCOPE = {"V01", "V02", "V09", "N01", "N02"}

PL_HEADER = "shift_start,shift,machine_id,units_produced,units_nonconforming,units_reworked,product_id,batch_id"
PL_ROW = "2026-03-10T22:00:00,night,M02,820,17,5,PCB-A,PST-2603-01"
ML_HEADER = "timestamp,machine_id,event_type,parameter,old_value,new_value,operator_id,note"
SS_HEADER = "date,shift,machine_id,operator_id,is_substitute"


def _key(i):
    return (i["code"], i["severity"], i["table"], i["row"], i["column"], i["value"])


def _scope(issues):
    return [i for i in issues if i["code"] in SCOPE]


def _match(issue, expected):
    """expected = (code, severity, table, row, column, value); value '*' = not compared."""
    return all(e == "*" or g == e for g, e in zip(_key(issue), expected, strict=True))


def assert_scope(issues, expected):
    got = _scope(issues)
    assert len(got) == len(expected), [_key(i) for i in got]
    left = list(got)
    for e in expected:
        hit = next((g for g in left if _match(g, e)), None)
        assert hit is not None, (e, [_key(i) for i in got])
        left.remove(hit)


def make_dir(tmp_path, **files):
    """Copy the valid template set, then replace files. A value None deletes the file; bytes/str replace."""
    d = tmp_path / "data"
    shutil.copytree(VALID, d)
    for name, content in files.items():
        f = d / name
        if content is None:
            f.unlink()
        elif isinstance(content, bytes):
            f.write_bytes(content)
        else:
            f.write_text(content, encoding="utf-8")
    return d


def run(d, cfg=CFG):
    return validate_directory(d, cfg)


# ---- valid templates and D2 invalid sets ------------------------------------------------------------------


def test_valid_templates_have_no_part1_items():
    assert _scope(run(VALID)) == []


E = "error"
W = "warning"
# README of data/templates, section 4 (value '*' = contract does not fix it). In-scope codes only.
D2_EXPECTED = {
    "V01a_missing_file": [("V01", E, "sop", None, None, "sop.csv")],
    "V01b_empty_file": [("V01", E, "sop", None, None, "*")],
    "V01c_header_only": [("V01", E, "sop", None, None, "*")],
    "V01d_missing_column": [("V01", E, "production_log", None, "units_nonconforming", "*")],
    "V01d_wrong_case": [
        ("V01", E, "production_log", None, "shift_start", "*"),
        ("N02", W, "production_log", None, "Shift_Start", "*"),
    ],
    "V01e_duplicate_column": [("V01", E, "production_log", None, "product_id", "*")],
    "V02_int_decimal": [("V02", E, "production_log", 9, "units_produced", "820.0")],
    "V02_conditional_empty": [("V02", E, "machine_log", 4, "parameter", "")],
    "V02_row_cell_count": [("V02", E, "production_log", 9, None, "*")],
    "V02_bool": [("V02", E, "shift_schedule", 9, "is_substitute", "TRUE")],
    "V02_date": [("V02", E, "shift_schedule", 2, "date", "2026-02-30")],
    "V09a_header": [
        ("V09", E, "shift_schedule", None, "operator_name", "*"),
        ("N02", W, "shift_schedule", None, "operator_name", "*"),
    ],
    "V09b_operator_value": [("V09", E, "shift_schedule", 3, "operator_id", "Nguyen Van A")],
}


@pytest.mark.parametrize("name", sorted(D2_EXPECTED))
def test_d2_set_gives_exactly_the_named_code(name):
    issues = run(INVALID / name)
    assert_scope(issues, D2_EXPECTED[name])
    assert {i["code"] for i in issues if i["code"].startswith("V") and i["code"] in SCOPE} == {
        D2_EXPECTED[name][0][0]
    }


def test_every_d2_v01_v02_v09_set_is_covered_by_a_test():
    names = {p.name for p in INVALID.iterdir() if p.name[:3] in ("V01", "V02", "V09")}
    assert names == set(D2_EXPECTED)


@pytest.mark.parametrize("name", sorted(p.name for p in INVALID.iterdir() if p.name[:3] not in ("V01", "V02", "V09")))
def test_other_d2_sets_have_no_part1_items(name):
    """No false positive of part 1 on sets built for V03-V08."""
    assert _scope(run(INVALID / name)) == []


# ---- contract examples V01 --------------------------------------------------------------------------------


def test_v01_pass_header_only_required_columns(tmp_path):
    d = make_dir(tmp_path, **{"production_log.csv": "shift_start,shift,machine_id,units_produced,units_nonconforming\n" + "2026-03-10T22:00:00,night,M02,820,17\n"})
    assert _scope(run(d)) == []


def test_v01_violation_d_missing_required_column(tmp_path):
    d = make_dir(tmp_path, **{"production_log.csv": "shift_start,shift,machine_id,units_produced\n2026-03-10T22:00:00,night,M02,820\n"})
    assert_scope(run(d), [("V01", E, "production_log", None, "units_nonconforming", "*")])


def test_v01_shift_start_wrong_case_gives_missing_and_n02(tmp_path):
    d = make_dir(
        tmp_path,
        **{"production_log.csv": "Shift_Start,shift,machine_id,units_produced,units_nonconforming\n2026-03-10T22:00:00,night,M02,820,17\n"},
    )
    assert_scope(
        run(d),
        [("V01", E, "production_log", None, "shift_start", "*"), ("N02", W, "production_log", None, "Shift_Start", "*")],
    )


def test_v01_every_conditional_b_column_must_be_in_header(tmp_path):
    d = make_dir(tmp_path, **{"machine_log.csv": "timestamp,machine_id,event_type\n2026-03-10T22:05:00,M02,note\n"})
    assert_scope(
        run(d),
        [("V01", E, "machine_log", None, c, "*") for c in ("parameter", "old_value", "new_value")],
    )


def test_v01_missing_columns_one_item_each(tmp_path):
    d = make_dir(tmp_path, **{"sop.csv": "sop_id,version\nSOP-1,1\n"})
    assert_scope(run(d), [("V01", E, "sop", None, c, "*") for c in ("title", "step_no", "step_text")])


def test_v01_optional_table_absent_is_fine_but_empty_file_is_v01(tmp_path):
    d = make_dir(tmp_path, **{"material_batches.csv": None})
    assert _scope(run(d)) == []
    d2 = make_dir(tmp_path / "x", **{"material_batches.csv": b""})
    assert_scope(run(d2), [("V01", E, "material_batches", None, None, "*")])


def test_v01_optional_table_header_only_is_valid(tmp_path):
    d = make_dir(tmp_path, **{"material_batches.csv": "batch_id,material_id,supplier_id,received_date\n"})
    assert _scope(run(d)) == []


def test_v01_only_blank_lines_is_empty_and_blank_data_lines_are_no_data(tmp_path):
    d = make_dir(tmp_path, **{"sop.csv": "\n   \n"})
    assert_scope(run(d), [("V01", E, "sop", None, None, "*")])
    d2 = make_dir(tmp_path / "y", **{"sop.csv": "sop_id,version,title,step_no,step_text\n\n\n"})
    assert_scope(run(d2), [("V01", E, "sop", None, None, "*")])


def test_v01_two_duplicate_names_give_two_items_and_no_n02(tmp_path):
    header = PL_HEADER + ",product_id,batch_id"
    d = make_dir(tmp_path, **{"production_log.csv": header + "\n" + PL_ROW + ",PCB-A,PST-2603-01\n"})
    assert_scope(
        run(d),
        [("V01", E, "production_log", None, "product_id", "*"), ("V01", E, "production_log", None, "batch_id", "*")],
    )


def test_duplicate_required_column_is_skipped_by_other_rules(tmp_path):
    """units_produced twice: V01 once; the second value 'abc' is not read, so no V02 for it."""
    header = "shift_start,shift,machine_id,units_produced,units_nonconforming,units_produced"
    d = make_dir(tmp_path, **{"production_log.csv": header + "\n2026-03-10T22:00:00,night,M02,820,17,abc\n"})
    assert_scope(run(d), [("V01", E, "production_log", None, "units_produced", "*")])


def test_table_level_v01_skips_all_other_rules_on_that_table(tmp_path):
    # header-only required table: not even V09 on its header
    d = make_dir(tmp_path, **{"sop.csv": "sop_id,version,title,step_no,step_text,full_name,extra\n"})
    assert_scope(run(d), [("V01", E, "sop", None, None, "*")])


def test_file_names_are_case_sensitive_even_on_case_insensitive_fs(tmp_path):
    d = make_dir(tmp_path, **{"sop.csv": None, "production_log.csv": None})
    (d / "Sop.csv").write_text("sop_id,version,title,step_no,step_text\n", encoding="utf-8")
    (d / "Production_Log.csv").write_text(PL_HEADER + "\n" + PL_ROW + "\n", encoding="utf-8")
    assert_scope(
        run(d),
        [
            ("V01", E, "sop", None, None, "sop.csv"),
            ("V01", E, "production_log", None, None, "production_log.csv"),
            ("N01", "*", "Sop.csv", None, None, "*"),
            ("N01", "*", "Production_Log.csv", None, None, "*"),
        ],
    )


def test_all_four_required_files_missing(tmp_path):
    empty = tmp_path / "e"
    empty.mkdir()
    assert_scope(
        run(empty),
        [("V01", E, t, None, None, f"{t}.csv") for t in ("production_log", "machine_log", "shift_schedule", "sop")],
    )


# ---- contract examples V02 --------------------------------------------------------------------------------


def test_v02_pass_and_violation_production_log(tmp_path):
    d = make_dir(tmp_path, **{"production_log.csv": PL_HEADER + "\n" + PL_ROW + "\n"})
    assert _scope(run(d)) == []
    bad = PL_ROW.replace(",820,", ",820.0,")
    d2 = make_dir(tmp_path / "b", **{"production_log.csv": PL_HEADER + "\n" + bad + "\n"})
    assert_scope(run(d2), [("V02", E, "production_log", 2, "units_produced", "820.0")])


def test_v02_machine_log_pass_and_conditional_violation(tmp_path):
    ok = "2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,180,195,OP-SUB01,"
    d = make_dir(tmp_path, **{"machine_log.csv": ML_HEADER + "\n" + ok + "\n"})
    assert _scope(run(d)) == []
    bad = "2026-03-10T22:05:00,M02,setpoint_change,,180,195,OP-SUB01,"
    d2 = make_dir(tmp_path / "b", **{"machine_log.csv": ML_HEADER + "\n" + bad + "\n"})
    assert_scope(run(d2), [("V02", E, "machine_log", 2, "parameter", "")])


@pytest.mark.parametrize(
    "kind,col,good,bad_values",
    [
        ("int", "units_produced", "820", ["820.0", "8.2e2", "abc", "-", "1 2"]),
        ("datetime", "shift_start", "2026-03-10T22:00:00", [
            "2026-03-10 22:00", "2026-03-10T22:00:00+07:00", "2026-03-10T24:00:00", "2026-02-30T22:00:00", "2026-03-10T22:00"]),
    ],
)
def test_v02_types_production_log(tmp_path, kind, col, good, bad_values):
    cols = PL_HEADER.split(",")
    base = PL_ROW.split(",")
    i = cols.index(col)

    def with_value(v):
        cells = list(base)
        cells[i] = v
        return PL_HEADER + "\n" + ",".join(cells) + "\n"

    assert _scope(run(make_dir(tmp_path / "ok", **{"production_log.csv": with_value(good)}))) == []
    for n, v in enumerate(bad_values):
        d = make_dir(tmp_path / f"b{n}", **{"production_log.csv": with_value(v)})
        assert_scope(run(d), [("V02", E, "production_log", 2, col, v)])


@pytest.mark.parametrize(
    "value,ok",
    [("195", True), ("180.5", True), ("-3", True), ("180,5", False), ("1e2", False), (".5", False), ("NaN", False), ("inf", False)],
)
def test_v02_float_forms(tmp_path, value, ok):
    row = f"2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,{value},195,OP-SUB01,"
    # a quoted comma stays one cell
    d = make_dir(tmp_path, **{"machine_log.csv": ML_HEADER + "\n" + (row if "," not in value else row.replace(value, f'"{value}"')) + "\n"})
    got = _scope(run(d))
    if ok:
        assert got == []
    else:
        assert_scope(got, [("V02", E, "machine_log", 2, "old_value", value)])


@pytest.mark.parametrize("value,ok", [("true", True), ("false", True), ("TRUE", False), ("1", False), ("yes", False)])
def test_v02_bool_forms(tmp_path, value, ok):
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + f"\n2026-03-10,night,M02,OP-SUB01,{value}\n"})
    got = _scope(run(d))
    if ok:
        assert got == []
    else:
        assert_scope(got, [("V02", E, "shift_schedule", 2, "is_substitute", value)])


@pytest.mark.parametrize("value", ["10/03/2026", "2026-3-10", "2026-02-30", "2026-13-01", ""])
def test_v02_date_forms(tmp_path, value):
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + f"\n{value},night,M02,OP-SUB01,true\n"})
    assert_scope(run(d), [("V02", E, "shift_schedule", 2, "date", value)])


def test_v02_empty_required_cell_and_optional_empty_ok(tmp_path):
    # batch_id (T) empty is fine; units_produced (B) empty is V02 with value ""
    row = "2026-03-10T22:00:00,night,M02,,17,,,"
    d = make_dir(tmp_path, **{"production_log.csv": PL_HEADER + "\n" + row + "\n"})
    assert_scope(run(d), [("V02", E, "production_log", 2, "units_produced", "")])


def test_v02_machine_log_condition_per_event_type(tmp_path):
    rows = [
        "2026-03-12T07:30:00,M02,program_change,,,,OP-017,PRG-B12",  # other types: skipped
        "2026-03-12T07:31:00,M02,note,abc,xyz,!!,OP-017,garbage ignored",  # not checked, even V02
        "2026-03-12T09:14:00,M01,alarm,zone3_setpoint_c,,188.4,,x",  # alarm: old_value ignored
        "2026-03-12T09:15:00,M01,alarm,,,,,x",  # alarm with nothing: fine
        "2026-03-12T09:16:00,M01,alarm,zone3_setpoint_c,,188,4,,x",  # 9 cells -> row shape
        "2026-03-12T09:17:00,M01,alarm,zone3_setpoint_c,,1e2,,x",  # alarm new_value format checked
        "2026-03-12T09:18:00,M01,setpoint_change,zone3_setpoint_c,180,,,x",  # new_value empty B
    ]
    d = make_dir(tmp_path, **{"machine_log.csv": ML_HEADER + "\n" + "\n".join(rows) + "\n"})
    assert_scope(
        run(d),
        [
            ("V02", E, "machine_log", 6, None, "*"),
            ("V02", E, "machine_log", 7, "new_value", "1e2"),
            ("V02", E, "machine_log", 8, "new_value", ""),
        ],
    )


def test_v02_cell_count_wrong_both_ways_and_row_skipped_by_others(tmp_path):
    rows = [PL_ROW + ",extra", "2026-03-10T22:00:00,night,M02"]
    d = make_dir(tmp_path, **{"production_log.csv": PL_HEADER + "\n" + "\n".join(rows) + "\n"})
    assert_scope(run(d), [("V02", E, "production_log", 2, None, "*"), ("V02", E, "production_log", 3, None, "*")])


def test_v02_not_utf8_is_table_level_and_skips_the_table(tmp_path):
    d = make_dir(tmp_path, **{"sop.csv": b"sop_id,version\n\xff\xfe\xfa,1\n"})
    assert_scope(run(d), [("V02", E, "sop", None, None, "*")])


def test_v02_all_errors_reported_not_only_the_first(tmp_path):
    bad = [PL_ROW.replace(",820,", ",x,"), PL_ROW.replace(",17,", ",y,"), PL_ROW.replace("night", "night")]
    d = make_dir(tmp_path, **{"production_log.csv": PL_HEADER + "\n" + "\n".join(bad) + "\n"})
    assert_scope(
        run(d),
        [("V02", E, "production_log", 2, "units_produced", "x"), ("V02", E, "production_log", 3, "units_nonconforming", "y")],
    )


# ---- contract examples V09 + criterion 2 ------------------------------------------------------------------


def test_v09_header_pass_and_violation(tmp_path):
    assert _scope(run(make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + "\n2026-03-10,night,M02,OP-SUB01,true\n"}))) == []
    d = make_dir(
        tmp_path / "b",
        **{"shift_schedule.csv": "date,shift,machine_id,operator_id,operator_name,is_substitute\n2026-03-10,night,M02,OP-SUB01,,true\n"},
    )
    assert_scope(
        run(d),
        [("V09", E, "shift_schedule", None, "operator_name", "*"), ("N02", W, "shift_schedule", None, "operator_name", "*")],
    )


def test_v09_value_violation(tmp_path):
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + "\n2026-03-10,night,M02,Nguyen Van A,true\n"})
    assert_scope(run(d), [("V09", E, "shift_schedule", 2, "operator_id", "Nguyen Van A")])


@pytest.mark.parametrize("col", ["operator_name", "OperatorName", "Full Name", "email_addr", "phone", "product_name", "DOB", "fullName"])
def test_v09_blocked_extra_column_names(tmp_path, col):
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + f",{col}\n2026-03-10,night,M02,OP-SUB01,true,\n"})
    assert_scope(run(d), [("V09", E, "shift_schedule", None, col, "*"), ("N02", W, "shift_schedule", None, col, "*")])


@pytest.mark.parametrize("col", ["username", "filename", "namespace", "Shift_Start", "note_text"])
def test_v09_names_not_blocked(tmp_path, col):
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + f",{col}\n2026-03-10,night,M02,OP-SUB01,true,\n"})
    assert [i["code"] for i in _scope(run(d))] == ["N02"]


def test_v09_applies_to_contract_columns_too_by_config(tmp_path):
    """Tokens come from the config: with 'shift' as a token, the contract column 'shift' is blocked."""
    cfg = CFG.model_copy(update={"validate_": CFG.validate_.model_copy(update={"pii_tokens": ["shift"]})})
    issues = run(VALID, cfg)
    cols = {(i["table"], i["column"]) for i in issues if i["code"] == "V09"}
    # whole words only: 'shift_start' splits into shift + start, so it is blocked too
    assert cols == {("production_log", "shift"), ("production_log", "shift_start"), ("shift_schedule", "shift")}


def test_v09_operator_pattern_whole_match_and_case(tmp_path):
    rows = ["2026-03-10,night,M01,op-017,false", "2026-03-10,night,M02,OP-017x!,false", "2026-03-10,night,M03,OP-017,false"]
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + "\n" + "\n".join(rows) + "\n"})
    assert_scope(
        run(d),
        [("V09", E, "shift_schedule", 2, "operator_id", "op-017"), ("V09", E, "shift_schedule", 3, "operator_id", "OP-017x!")],
    )


def test_v09_operator_pattern_from_config_and_machine_log(tmp_path):
    cfg = CFG.model_copy(update={"validate_": CFG.validate_.model_copy(update={"operator_id_pattern": r"^W[0-9]+$"})})
    d = make_dir(
        tmp_path,
        **{
            "machine_log.csv": ML_HEADER + "\n2026-03-10T22:05:00,M02,note,,,,W12,\n2026-03-10T22:06:00,M02,note,,,,OP-017,\n2026-03-10T22:07:00,M02,note,,,,,\n"
        },
    )
    got = [i for i in run(d, cfg) if i["table"] == "machine_log"]
    assert [(i["code"], i["row"], i["value"]) for i in got] == [("V09", 3, "OP-017")]


# ---- N01, N02 ---------------------------------------------------------------------------------------------


def test_n01_extra_files_are_not_read(tmp_path):
    d = make_dir(tmp_path)
    (d / "kpi_log.csv").write_text("whatever,full_name\n1,2\n", encoding="utf-8")
    (d / "environment_log.csv").write_bytes(b"\xff\xff")
    (d / "notes.txt").write_text("x\n", encoding="utf-8")
    (d / "sub").mkdir()
    got = _scope(run(d))
    assert sorted((i["code"], i["severity"], i["table"]) for i in got) == [
        ("N01", W, "environment_log.csv"),
        ("N01", W, "kpi_log.csv"),
        ("N01", W, "notes.txt"),
    ]


def test_n02_training_level_and_extra_columns(tmp_path):
    d = make_dir(tmp_path, **{"shift_schedule.csv": SS_HEADER + ",training_level,zzz\n2026-03-10,night,M02,OP-SUB01,true,2,\n"})
    assert_scope(
        run(d),
        [("N02", W, "shift_schedule", None, "training_level", "*"), ("N02", W, "shift_schedule", None, "zzz", "*")],
    )


# ---- reading (criterion 3) --------------------------------------------------------------------------------


def test_bom_and_padded_cells_are_read(tmp_path):
    text = "﻿" + " shift_start , shift,machine_id,units_produced,units_nonconforming\n 2026-03-10T22:00:00 ,night, M02 , 820 ,17\n"
    t = parse_table("production_log", text.encode("utf-8"))
    assert t.status == "ok" and t.header[0] == "shift_start"
    assert t.rows[0].cells["units_produced"] == "820" and t.rows[0].cells["machine_id"] == "M02"
    d = make_dir(tmp_path, **{"production_log.csv": text.encode("utf-8")})
    assert _scope(run(d)) == []


def test_blank_lines_skipped_but_counted(tmp_path):
    rows = [PL_ROW, "", "   ", PL_ROW.replace(",820,", ",bad,")]
    d = make_dir(tmp_path, **{"production_log.csv": PL_HEADER + "\n" + "\n".join(rows) + "\n"})
    assert_scope(run(d), [("V02", E, "production_log", 5, "units_produced", "bad")])
    t = parse_table("production_log", (PL_HEADER + "\n" + "\n".join(rows) + "\n").encode())
    assert [r.num for r in t.rows] == [2, 5]


def test_quoted_fields_rfc4180_and_row_starts_where_record_starts(tmp_path):
    note = '"line one\nline two, with comma ""quoted"""'
    rows = [
        "2026-03-12T07:30:00,M02,note,,,," + "OP-017," + note,
        "2026-03-12T07:31:00,M02,note,,,,OP-017,x",
        "2026-03-12T07:32:00,M02,setpoint_change,zone3_setpoint_c,abc,195,OP-017,",
    ]
    d = make_dir(tmp_path, **{"machine_log.csv": ML_HEADER + "\n" + "\n".join(rows) + "\n"})
    assert_scope(run(d), [("V02", E, "machine_log", 5, "old_value", "abc")])


def test_crlf_line_endings(tmp_path):
    text = (PL_HEADER + "\r\n" + PL_ROW + "\r\n" + PL_ROW.replace(",820,", ",x,") + "\r\n").encode()
    d = make_dir(tmp_path, **{"production_log.csv": text})
    assert_scope(run(d), [("V02", E, "production_log", 3, "units_produced", "x")])


# ---- repeatability, defaults ------------------------------------------------------------------------------


def test_repeated_calls_do_not_leak_state(tmp_path):
    first = run(INVALID / "V09a_header")
    run(INVALID / "V01a_missing_file")
    second = run(INVALID / "V09a_header")
    assert [_key(i) for i in first] == [_key(i) for i in second]
    assert _scope(run(VALID)) == []


def test_default_config_when_none_given():
    assert [_key(i) for i in validate_directory(INVALID / "V02_bool")] == [_key(i) for i in run(INVALID / "V02_bool")]


def test_report_item_has_all_fields():
    issue = run(INVALID / "V02_bool")[0]
    assert set(issue) == {"code", "severity", "table", "row", "column", "value", "fix"}


def test_does_not_modify_source_files(tmp_path):
    d = make_dir(tmp_path, **{"production_log.csv": b"\xef\xbb\xbf" + (PL_HEADER + "\n" + PL_ROW + "\n").encode()})
    before = {p.name: p.read_bytes() for p in d.iterdir()}
    run(d)
    assert {p.name: p.read_bytes() for p in d.iterdir()} == before


def test_module_hardcodes_no_config_names():
    text = (ROOT / "backend/sandbox/validate.py").read_text(encoding="utf-8")
    for name in ("defect_rate", "rework_rate", "zone3_setpoint_c", "M01", "morning", "setpoint_change"):
        assert name not in text
