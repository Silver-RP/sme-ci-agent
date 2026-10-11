"""Input validation of the data contract (docs/schema/data_contract.md section 3 and 4), part 1.

Pure functions: a directory of CSV files (or already read tables) plus the domain config give a list
of report items (dicts with ``code``, ``severity``, ``table``, ``row``, ``column``, ``value``, ``fix``).
Part 1 covers the general rules (4.0), V01, V02, V09, N01, N02. Rules V03-V08, N03, N04 are added later
on top of the same ``Validation`` object (``tables``, ``issues``, ``bad_cells``).

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

from backend.domain_config import DomainConfig, load_domain_config

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
        self._n01_n02()
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
