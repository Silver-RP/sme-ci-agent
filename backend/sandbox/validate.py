"""Input validation of the data contract (docs/schema/data_contract.md section 3 and 4), part 1.

Pure functions: a directory of CSV files (or already read tables) plus the domain config give a list
of report items (dicts with ``code``, ``severity``, ``table``, ``row``, ``column``, ``value``, ``fix``).
Rules run in the order of 4.0: V01, V02, V09, V03-V08, N01, N02, N03, N04 (N03/N04 come from
``kpi_derive.derive_kpi_log``). The ``Validation`` object keeps ``tables``, ``issues``, ``bad_cells``.

Table and column names here are the contract itself (section 2); names of KPIs, machines, shifts,
parameters, event types and thresholds come from the domain config.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox.kpi_derive import derive_kpi_log

# ---- contract tables (section 2): column -> (type, requirement) -------------------------------------
# requirement: "B" required, "T" optional, "cond" depends on machine_log.event_type (see _event_mode).
_B, _T, _COND = "B", "T", "cond"
TABLE_COLUMNS: dict[str, dict[str, tuple[str, str]]] = {
    "production_log": {
        "shift_start": ("datetime", _B),
        "shift": ("str", _B),
        "machine_id": ("str", _B),
        "units_produced": ("int", _B),
        "units_nonconforming": ("int", _B),
        "units_reworked": ("int", _T),
        "product_id": ("str", _T),
        "batch_id": ("str", _T),
    },
    "machine_log": {
        "timestamp": ("datetime", _B),
        "machine_id": ("str", _B),
        "event_type": ("str", _B),
        "parameter": ("str", _COND),
        "old_value": ("float", _COND),
        "new_value": ("float", _COND),
        "operator_id": ("str", _T),
        "note": ("str", _T),
    },
    "shift_schedule": {
        "date": ("date", _B),
        "shift": ("str", _B),
        "machine_id": ("str", _B),
        "operator_id": ("str", _B),
        "is_substitute": ("bool", _B),
    },
    "material_batches": {
        "batch_id": ("str", _B),
        "material_id": ("str", _B),
        "supplier_id": ("str", _B),
        "received_date": ("date", _B),
        "expiry_date": ("date", _T),
        "qc_result": ("str", _T),
    },
    "sop": {
        "sop_id": ("str", _B),
        "version": ("int", _B),
        "title": ("str", _B),
        "step_no": ("int", _B),
        "step_text": ("str", _B),
    },
}
REQUIRED_TABLES: tuple[str, ...] = ("production_log", "machine_log", "shift_schedule", "sop")
OPERATOR_TABLES: tuple[str, ...] = ("shift_schedule", "machine_log")  # tables with an operator_id column
ALARM_EVENT = "alarm"  # contract 2.2: parameter / new_value are optional for this event type
QC_RESULTS: tuple[str, ...] = ("pass", "fail", "conditional")  # contract 2.4 (V03)
# Natural keys (V04), in the order of the contract; the first column is the one reported.
KEYS: dict[str, tuple[str, ...]] = {
    "production_log": ("shift_start", "machine_id"),
    "shift_schedule": ("date", "shift", "machine_id"),
    "material_batches": ("batch_id",),
    "sop": ("sop_id", "version", "step_no"),
}

_INT_RE = re.compile(r"-?[0-9]+")
_FLOAT_RE = re.compile(r"-?[0-9]+(\.[0-9]+)?")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATETIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")


def file_name(table: str) -> str:
    return f"{table}.csv"


# ---- reading ------------------------------------------------------------------------------------------


@dataclass
class Row:
    """One data record. ``num`` is the physical CSV line where it starts (header = 1).
    ``cells`` maps usable (uniquely named) columns to the stripped value; it is ``None`` when the record
    has a different number of cells than the header (V02 on the row; no other rule reads it)."""

    num: int
    cells: dict[str, str] | None


@dataclass
class TableData:
    name: str
    status: str  # "ok" | "missing" | "empty" (no header) | "not_utf8" | "unreadable"
    header: list[str] = field(default_factory=list)  # stripped names, in file order, duplicates kept
    rows: list[Row] = field(default_factory=list)  # blank lines already removed

    @property
    def duplicates(self) -> list[str]:
        seen: set[str] = set()
        dup: list[str] = []
        for h in self.header:
            if h in seen and h not in dup:
                dup.append(h)
            seen.add(h)
        return dup

    @property
    def usable_columns(self) -> list[str]:
        """Header names that occur exactly once (a duplicated name is as good as missing)."""
        dup = set(self.duplicates)
        return [h for h in self.header if h not in dup]


def parse_table(name: str, raw: bytes) -> TableData:
    """Parse the bytes of one CSV file (RFC 4180, BOM accepted, cells and names stripped)."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return TableData(name, "not_utf8")
    reader = csv.reader(io.StringIO(text, newline=""))
    records: list[tuple[int, list[str]]] = []
    prev_end = 0
    try:
        for rec in reader:
            records.append((prev_end + 1, rec))
            prev_end = reader.line_num
    except csv.Error:
        return TableData(name, "unreadable")

    def blank(rec: list[str]) -> bool:
        return all(not c.strip() for c in rec) and len(rec) <= 1

    live = [(n, r) for n, r in records if not blank(r)]
    if not live:
        return TableData(name, "empty")
    header = [c.strip() for c in live[0][1]]
    table = TableData(name, "ok", header=header)
    usable = set(table.usable_columns)
    for num, rec in live[1:]:
        if len(rec) != len(header):
            table.rows.append(Row(num, None))
            continue
        cells = {h: c.strip() for h, c in zip(header, rec, strict=True) if h in usable}
        table.rows.append(Row(num, cells))
    return table


def read_directory(path: str | Path) -> tuple[dict[str, TableData], list[str]]:
    """Read exactly the 5 contract files. Returns ``(tables, extra_file_names)``."""
    root = Path(path)
    tables: dict[str, TableData] = {}
    # Exact (case-sensitive) comparison against real directory entries, so it also holds on
    # case-insensitive filesystems where root / "sop.csv" would open "Sop.csv".
    present = {p.name for p in root.iterdir() if p.is_file()}
    for name in TABLE_COLUMNS:
        fn = file_name(name)
        tables[name] = parse_table(name, (root / fn).read_bytes()) if fn in present else TableData(name, "missing")
    known = {file_name(n) for n in TABLE_COLUMNS}
    extras = sorted(present - known)
    return tables, extras


# ---- type checks (1.1) ---------------------------------------------------------------------------------


def _valid_type(kind: str, value: str) -> bool:
    if kind == "str":
        return True
    if kind == "int":
        return _INT_RE.fullmatch(value) is not None
    if kind == "float":
        return _FLOAT_RE.fullmatch(value) is not None
    if kind == "bool":
        return value in ("true", "false")
    try:
        if kind == "date":
            if _DATE_RE.fullmatch(value) is None:
                return False
            date.fromisoformat(value)
            return True
        if kind == "datetime":
            if _DATETIME_RE.fullmatch(value) is None:
                return False
            datetime.fromisoformat(value)  # format already fixed by the regex; this checks the date/time exist
            return True
    except ValueError:
        return False
    raise ValueError(f"unknown type {kind}")


_TYPE_FIX = {
    "int": "a whole number such as 820 (no decimals, no exponent)",
    "float": "a number with '.' as decimal mark, such as 180.5",
    "bool": "true or false (lower case)",
    "date": "a real date as YYYY-MM-DD",
    "datetime": "a real local time as YYYY-MM-DDTHH:MM:SS, without time zone",
}


def _parse(kind: str, value: str):
    """Parse a value already accepted by ``_valid_type`` (used to compare keys by parsed value)."""
    if kind == "int":
        return int(value)
    if kind == "date":
        return date.fromisoformat(value)
    if kind == "datetime":
        return datetime.fromisoformat(value)
    return value


def split_words(name: str) -> list[str]:
    """V09 (a): split on lower->upper boundaries and on every character that is not a letter/digit."""
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return re.findall(r"[^\W_]+", spaced.lower())


# ---- validation ---------------------------------------------------------------------------------------


class Validation:
    """State of one validation run: the tables, the report items and the cells that already failed."""

    def __init__(self, tables: dict[str, TableData], extras: list[str], cfg: DomainConfig) -> None:
        self.tables = tables
        self.extras = extras
        self.cfg = cfg
        self.issues: list[dict] = []
        # (table, row, column) of cells already reported by V02 or V09: later rules skip them (4.0).
        self.bad_cells: set[tuple[str, int, str]] = set()
        self._table_level_failed: set[str] = set()  # tables skipped by every other rule (4.0)

    def add(
        self,
        code: str,
        severity: str,
        table: str,
        *,
        row: int | None = None,
        column: str | None = None,
        value: str | None = None,
        fix: str = "",
    ) -> None:
        self.issues.append(
            {
                "code": code,
                "severity": severity,
                "table": table,
                "row": row,
                "column": column,
                "value": value,
                "fix": fix,
            }
        )

    def usable(self, table: str) -> bool:
        """The table was read and passed the table-level checks (V01 a-c, UTF-8)."""
        t = self.tables.get(table)
        return t is not None and t.status == "ok" and table not in self._table_level_failed

    # -- rules -------------------------------------------------------------------------------------

    def run(self) -> list[dict]:
        self._v01()
        self._v02()
        self._v09()
        self._v03()
        self._v04()
        self._v05()
        self._v06()
        self._v07()
        self._v08()
        self._n01_n02()
        self._n03_n04()
        return self.issues

    def _v01(self) -> None:
        for name, t in self.tables.items():
            required = name in REQUIRED_TABLES
            fname = file_name(name)
            if t.status == "missing":
                if required:
                    self.add("V01", "error", name, value=fname, fix=f"Provide {fname}.")
                self._table_level_failed.add(name)
                continue
            if t.status == "not_utf8":
                self.add("V02", "error", name, fix=f"Save {fname} as UTF-8.")
                self._table_level_failed.add(name)
                continue
            if t.status == "unreadable":
                self.add("V02", "error", name, fix=f"{fname} is not valid CSV (RFC 4180).")
                self._table_level_failed.add(name)
                continue
            if t.status == "empty":
                self.add("V01", "error", name, value=fname, fix=f"{fname} is empty: add the header line.")
                self._table_level_failed.add(name)
                continue
            if required and not t.rows:
                self.add("V01", "error", name, value=fname, fix=f"{fname} has a header but no data rows.")
                self._table_level_failed.add(name)
                continue
            present = set(t.header)
            for col in TABLE_COLUMNS[name]:
                if col not in present and TABLE_COLUMNS[name][col][1] != _T:
                    self.add("V01", "error", name, column=col, fix=f"Add the required column '{col}'.")
            for col in t.duplicates:
                self.add("V01", "error", name, column=col, fix=f"Column '{col}' appears more than once.")

    @staticmethod
    def _event_mode(col: str, event: str | None, setpoint_event: str) -> str:
        """Requirement of a machine_log conditional column for one row: "B", "T" or "skip"."""
        if event == setpoint_event:
            return _B
        if event == ALARM_EVENT and col in ("parameter", "new_value"):
            return _T
        return "skip"

    def _v02(self) -> None:
        setpoint_event = self.cfg.signals.setpoint_event
        for name, t in self.tables.items():
            if not self.usable(name):
                continue
            specs = TABLE_COLUMNS[name]
            cols = [c for c in t.usable_columns if c in specs]
            for row in t.rows:
                if row.cells is None:
                    self.add(
                        "V02",
                        "error",
                        name,
                        row=row.num,
                        fix=f"The row has a different number of cells than the header ({len(t.header)}).",
                    )
                    continue
                event = row.cells.get("event_type") if name == "machine_log" else None
                for col in cols:
                    kind, req = specs[col]
                    if req == _COND:
                        req = self._event_mode(col, event, setpoint_event)
                    if req == "skip":
                        continue
                    value = row.cells[col]
                    if value == "":
                        if req == _B:
                            self.add("V02", "error", name, row=row.num, column=col, value="", fix=f"'{col}' must not be empty.")
                            self.bad_cells.add((name, row.num, col))
                    elif not _valid_type(kind, value):
                        self.add(
                            "V02",
                            "error",
                            name,
                            row=row.num,
                            column=col,
                            value=value,
                            fix=f"'{col}' must be {_TYPE_FIX[kind]}.",
                        )
                        self.bad_cells.add((name, row.num, col))

    def _v09(self) -> None:
        tokens = {t.lower() for t in self.cfg.validate_.pii_tokens}
        pattern = re.compile(self.cfg.validate_.operator_id_pattern)
        for name, t in self.tables.items():
            if not self.usable(name):
                continue
            seen: set[str] = set()
            for col in t.header:
                if col in seen:
                    continue
                seen.add(col)
                if tokens.intersection(split_words(col)):
                    self.add(
                        "V09",
                        "error",
                        name,
                        column=col,
                        fix=f"Column '{col}' looks like personal data: remove it or rename it (use anonymous codes).",
                    )
            if name in OPERATOR_TABLES and "operator_id" in t.usable_columns:
                for row in t.rows:
                    if row.cells is None:
                        continue
                    value = row.cells["operator_id"]
                    if value and (name, row.num, "operator_id") not in self.bad_cells and not pattern.fullmatch(value):
                        self.add(
                            "V09",
                            "error",
                            name,
                            row=row.num,
                            column="operator_id",
                            value=value,
                            fix="Use an anonymous operator code that matches validate.operator_id_pattern.",
                        )
                        self.bad_cells.add((name, row.num, "operator_id"))

    # -- helpers for part 2 --------------------------------------------------------------------------

    def _cell(self, table: str, row: Row, col: str) -> str | None:
        """Value of a usable, non-empty cell that no earlier rule (V02, V09) rejected; else ``None``."""
        if row.cells is None or (table, row.num, col) in self.bad_cells:
            return None
        value = row.cells.get(col)
        return value or None

    def _cell_int(self, table: str, row: Row, col: str) -> int | None:
        v = self._cell(table, row, col)
        return int(v) if v is not None else None

    def _cell_float(self, table: str, row: Row, col: str) -> float | None:
        v = self._cell(table, row, col)
        return float(v) if v is not None else None

    def _cell_date(self, table: str, row: Row, col: str) -> date | None:
        v = self._cell(table, row, col)
        return date.fromisoformat(v) if v is not None else None

    def _cell_datetime(self, table: str, row: Row, col: str) -> datetime | None:
        v = self._cell(table, row, col)
        return datetime.fromisoformat(v) if v is not None else None

    def _rows(self, table: str) -> list[Row]:
        """Rows of a usable table that are split into cells (rows with a wrong cell count are skipped)."""
        if not self.usable(table):
            return []
        return [r for r in self.tables[table].rows if r.cells is not None]

    # -- V03 -----------------------------------------------------------------------------------------

    def _v03(self) -> None:
        self._v03_production_log()
        self._v03_machine_log()
        self._v03_material_batches()
        self._v03_sop()

    def _v03_production_log(self) -> None:
        name = "production_log"
        hours = self.cfg.plant.shift_start_hours
        counts = ("units_produced", "units_nonconforming", "units_reworked")
        for row in self._rows(name):
            values = {c: self._cell_int(name, row, c) for c in counts}
            for col, v in values.items():
                if v is not None and v < 0:
                    self.add("V03", "error", name, row=row.num, column=col, value=str(v), fix=f"'{col}' must not be negative.")
            produced = values["units_produced"]
            for col in ("units_nonconforming", "units_reworked"):
                v = values[col]
                if v is not None and produced is not None and v > produced:
                    self.add(
                        "V03",
                        "error",
                        name,
                        row=row.num,
                        column=col,
                        value=str(v),
                        fix=f"'{col}' must not be greater than units_produced ({produced}).",
                    )
            start = self._cell_datetime(name, row, "shift_start")
            shift = self._cell(name, row, "shift")
            if start is not None and shift in hours and (start.hour, start.minute, start.second) != (hours[shift], 0, 0):
                self.add(
                    "V03",
                    "error",
                    name,
                    row=row.num,
                    column="shift_start",
                    value=row.cells["shift_start"],
                    fix=f"A shift '{shift}' must start at {hours[shift]:02d}:00:00 (plant.shift_start_hours).",
                )

    def _v03_machine_log(self) -> None:
        name = "machine_log"
        limits = self.cfg.actions.limits
        for row in self._rows(name):
            if self._cell(name, row, "event_type") != self.cfg.signals.setpoint_event:
                continue
            parameter = self._cell(name, row, "parameter")
            if parameter not in limits:
                continue
            lim = limits[parameter]
            for col in ("old_value", "new_value"):
                v = self._cell_float(name, row, col)
                if v is not None and not lim.min <= v <= lim.max:
                    self.add(
                        "V03",
                        "error",
                        name,
                        row=row.num,
                        column=col,
                        value=row.cells[col],
                        fix=f"'{col}' must be within {lim.min:g}-{lim.max:g} for {parameter} (actions.limits).",
                    )

    def _v03_material_batches(self) -> None:
        name = "material_batches"
        for row in self._rows(name):
            received = self._cell_date(name, row, "received_date")
            expiry = self._cell_date(name, row, "expiry_date")
            if received is not None and expiry is not None and expiry < received:
                self.add(
                    "V03",
                    "error",
                    name,
                    row=row.num,
                    column="expiry_date",
                    value=row.cells["expiry_date"],
                    fix="'expiry_date' must not be before 'received_date'.",
                )
            qc = self._cell(name, row, "qc_result")
            if qc is not None and qc not in QC_RESULTS:
                self.add(
                    "V03",
                    "error",
                    name,
                    row=row.num,
                    column="qc_result",
                    value=qc,
                    fix=f"'qc_result' must be one of {', '.join(QC_RESULTS)}.",
                )

    def _v03_sop(self) -> None:
        name = "sop"
        groups: dict[tuple[str, int], list[Row]] = {}
        for row in self._rows(name):
            sop_id = self._cell(name, row, "sop_id")
            version = self._cell_int(name, row, "version")
            if version is not None and version < 1:
                self.add("V03", "error", name, row=row.num, column="version", value=str(version), fix="'version' must be 1 or more.")
            step = self._cell_int(name, row, "step_no")
            if step is not None and step < 1:
                self.add("V03", "error", name, row=row.num, column="step_no", value=str(step), fix="'step_no' must be 1 or more.")
            if sop_id is not None and version is not None:
                groups.setdefault((sop_id, version), []).append(row)
        for (sop_id, version), rows in groups.items():
            first_title = next((self._cell(name, r, "title") for r in rows if self._cell(name, r, "title") is not None), None)
            for row in rows:
                title = self._cell(name, row, "title")
                if first_title is not None and title is not None and title != first_title:
                    self.add(
                        "V03",
                        "error",
                        name,
                        row=row.num,
                        column="title",
                        value=title,
                        fix=f"'title' must be the same on every row of {sop_id} version {version}.",
                    )
            steps = {s for r in rows if (s := self._cell_int(name, r, "step_no")) is not None}
            if not steps:
                continue
            missing = [n for n in range(1, max(max(steps), 1) + 1) if n not in steps]
            if missing:
                self.add(
                    "V03",
                    "error",
                    name,
                    row=rows[0].num,
                    column="step_no",
                    value=", ".join(str(n) for n in missing),
                    fix=f"Steps of {sop_id} version {version} must be 1, 2, 3, ... without gaps.",
                )

    # -- V04 -----------------------------------------------------------------------------------------

    def _v04(self) -> None:
        for name, key_cols in KEYS.items():
            usable = set(self.tables[name].usable_columns) if self.usable(name) else set()
            if not set(key_cols) <= usable:
                continue
            first: dict[tuple, int] = {}
            for row in self._rows(name):
                parts = []
                for col in key_cols:
                    kind = TABLE_COLUMNS[name][col][0]
                    v = self._cell(name, row, col)
                    if v is None:
                        parts = []
                        break
                    parts.append(_parse(kind, v))
                if not parts:
                    continue
                key = tuple(parts)
                if key in first:
                    self.add(
                        "V04",
                        "error",
                        name,
                        row=row.num,
                        column=key_cols[0],
                        value=str(first[key]),
                        fix=f"The key ({', '.join(key_cols)}) repeats the row {first[key]}.",
                    )
                else:
                    first[key] = row.num

    # -- V05 -----------------------------------------------------------------------------------------

    def _v05(self) -> None:
        machines = set(self.cfg.plant.machines)
        shifts = set(self.cfg.plant.shifts)
        events = set(self.cfg.machine_log.event_types)
        parameters = set(self.cfg.actions.parameters)
        for name in ("production_log", "machine_log", "shift_schedule"):
            for row in self._rows(name):
                self._v05_code(name, row, "machine_id", machines, "plant.machines")
                if name != "machine_log":
                    self._v05_code(name, row, "shift", shifts, "plant.shifts")
                if name == "machine_log":
                    event = self._cell(name, row, "event_type")
                    self._v05_code(name, row, "event_type", events, "machine_log.event_types")
                    if event == self.cfg.signals.setpoint_event or event == ALARM_EVENT:
                        self._v05_code(name, row, "parameter", parameters, "actions.parameters")

    def _v05_code(self, table: str, row: Row, col: str, allowed: set[str], source: str) -> None:
        v = self._cell(table, row, col)
        if v is not None and v not in allowed:
            self.add("V05", "error", table, row=row.num, column=col, value=v, fix=f"'{col}' must be one of {source} (case sensitive).")

    # -- V06 -----------------------------------------------------------------------------------------

    def _v06(self) -> None:
        name = "production_log"
        shifts = self.cfg.plant.shifts
        hours = self.cfg.plant.shift_start_hours
        per_machine: dict[str, set[int]] = {}
        for row in self._rows(name):
            start = self._cell_datetime(name, row, "shift_start")
            shift = self._cell(name, row, "shift")
            machine = self._cell(name, row, "machine_id")
            if start is None or shift not in shifts or machine is None:
                continue
            per_machine.setdefault(machine, set()).add(start.date().toordinal() * len(shifts) + shifts.index(shift))
        if not per_machine:
            return
        lo = min(min(c) for c in per_machine.values())
        hi = max(max(c) for c in per_machine.values())
        limit = self.cfg.validate_.max_missing_shifts

        def label(cell: int) -> str:
            day, idx = divmod(cell, len(shifts))
            return f"{date.fromordinal(day).isoformat()}T{hours[shifts[idx]]:02d}:00:00"

        for machine, cells in per_machine.items():
            run_start = lo
            for cell in [*sorted(cells), hi + 1]:
                length = cell - run_start
                if length > limit:
                    self.add(
                        "V06",
                        "warning",
                        name,
                        column="machine_id",
                        value=f"{machine} {label(run_start)}/{label(cell - 1)} ({length})",
                        fix=f"{machine} has {length} shifts in a row without data (more than validate.max_missing_shifts).",
                    )
                run_start = cell + 1

    # -- V07 -----------------------------------------------------------------------------------------

    def _v07(self) -> None:
        sched = "shift_schedule"
        if self.usable(sched) and "operator_id" in self.tables[sched].usable_columns:
            known = {r.cells["operator_id"] for r in self._rows(sched) if r.cells["operator_id"]}
            self._v07_unknown("machine_log", "operator_id", known, "shift_schedule.operator_id")
        mb = self.tables["material_batches"]
        known_batches: set[str] | None = None
        if mb.status == "missing":
            known_batches = set()
        elif self.usable("material_batches") and "batch_id" in mb.usable_columns:
            known_batches = {r.cells["batch_id"] for r in self._rows("material_batches") if r.cells["batch_id"]}
        if known_batches is not None:
            self._v07_unknown("production_log", "batch_id", known_batches, "material_batches.batch_id")

    def _v07_unknown(self, table: str, col: str, known: set[str], source: str) -> None:
        reported: set[str] = set()
        for row in self._rows(table):
            v = self._cell(table, row, col)
            if v is not None and v not in known and v not in reported:
                reported.add(v)
                self.add("V07", "warning", table, row=row.num, column=col, value=v, fix=f"'{v}' is not in {source}.")

    # -- V08 -----------------------------------------------------------------------------------------

    def _v08(self) -> None:
        name = "production_log"
        days = [d.date() for r in self._rows(name) if (d := self._cell_datetime(name, r, "shift_start")) is not None]
        if not days:
            return
        length = (max(days) - min(days)).days + 1
        need = self.cfg.detect.reference_days + self.cfg.validate_.min_monitor_days
        if length < need:
            self.add(
                "V08",
                "warning",
                name,
                column="shift_start",
                value=str(length),
                fix=f"The history is {length} days; at least {need} (detect.reference_days + validate.min_monitor_days) are needed.",
            )

    # -- N03, N04 ------------------------------------------------------------------------------------

    def _n03_n04(self) -> None:
        name = "production_log"
        if not self.usable(name):
            return
        t = self.tables[name]
        rows = [r for r in t.rows if r.cells is not None]
        cols = [c for c in t.usable_columns if c in TABLE_COLUMNS[name]]
        data = {
            c: [None if (name, r.num, c) in self.bad_cells else (r.cells[c] or None) for r in rows] for c in cols
        }
        frame = pd.DataFrame(data, columns=cols, dtype=object)
        for c in ("shift_start", "shift", "machine_id"):
            if c not in frame.columns:
                frame[c] = None
        frame["shift_start"] = pd.to_datetime(frame["shift_start"], errors="coerce", format="%Y-%m-%dT%H:%M:%S")
        _, notes = derive_kpi_log(frame, self.cfg)
        for note in notes:
            row = note["row"]
            self.add(
                note["code"],
                "note",
                name,
                row=rows[row - 2].num if row is not None else None,
                column=note["column"],
                value=note["value"],
                fix="Information only: no action needed." if note["code"] == "N03" else "The KPI is not computed without this column.",
            )

    def _n01_n02(self) -> None:
        for extra in self.extras:
            self.add("N01", "warning", extra, fix="This file is not one of the 5 contract tables and is ignored.")
        for name, t in self.tables.items():
            if not self.usable(name):
                continue
            dup = set(t.duplicates)
            seen: set[str] = set()
            for col in t.header:
                if col in TABLE_COLUMNS[name] or col in dup or col in seen:
                    continue
                seen.add(col)
                self.add("N02", "warning", name, column=col, fix=f"Column '{col}' is not in the contract and is ignored.")


def validate_tables(
    tables: dict[str, TableData], cfg: DomainConfig | None = None, extras: list[str] | None = None
) -> list[dict]:
    """Validate already read tables. ``extras`` are names of files that are not contract tables."""
    return Validation(tables, list(extras or []), cfg or load_domain_config()).run()


def validate_directory(path: str | Path, cfg: DomainConfig | None = None) -> list[dict]:
    """Validate a directory of CSV files against the data contract; reads nothing but the 5 contract files."""
    tables, extras = read_directory(path)
    return validate_tables(tables, cfg, extras)
