"""Derive ``kpi_log`` from ``production_log`` (data contract 2.8).

For each KPI of the domain config, one row per ``production_log`` row:
``value = numerator / denominator``. KPI names and column names come from the config only.
"""

from __future__ import annotations

import pandas as pd

from backend.domain_config import DomainConfig
from backend.sandbox.schema import TABLE_SCHEMAS

_TABLE = "production_log"
_KPI_COLS = list(TABLE_SCHEMAS["kpi_log"])


def _empty() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.Series(dtype="datetime64[ns]"),
            "date": pd.Series(dtype="datetime64[ns]"),
            "shift": pd.Series(dtype="object"),
            "machine_id": pd.Series(dtype="object"),
            "kpi": pd.Series(dtype="object"),
            "value": pd.Series(dtype="float64"),
        }
    )[_KPI_COLS]


def derive_kpi_log(production_log: pd.DataFrame, cfg: DomainConfig) -> tuple[pd.DataFrame, list[dict]]:
    """Return ``(kpi_log, notes)``. Notes are contract items (severity ``note``):
    N03 for a row whose denominator is 0 (no ``kpi_log`` row), N04 for a KPI whose numerator
    (or denominator) column is absent (KPI not computed). ``row`` is the physical CSV row
    (header = 1) assuming rows are in file order."""
    notes: list[dict] = []
    frames: list[pd.DataFrame] = []
    pl = production_log.reset_index(drop=True)
    seen_n03: set[tuple[int, str]] = set()
    for order, kpi in enumerate(cfg.kpis):
        missing = next((c for c in (kpi.numerator, kpi.denominator) if c not in pl.columns), None)
        if missing is not None:
            notes.append(
                {
                    "code": "N04",
                    "severity": "note",
                    "table": _TABLE,
                    "row": None,
                    "column": missing,
                    "value": kpi.name,
                }
            )
            continue
        num = pd.to_numeric(pl[kpi.numerator], errors="coerce")
        den = pd.to_numeric(pl[kpi.denominator], errors="coerce")
        zero = den == 0
        for i in pl.index[zero]:
            if (int(i), kpi.denominator) not in seen_n03:
                seen_n03.add((int(i), kpi.denominator))
                notes.append(
                    {
                        "code": "N03",
                        "severity": "note",
                        "table": _TABLE,
                        "row": int(i) + 2,
                        "column": kpi.denominator,
                        "value": "0",
                    }
                )
        ok = (~zero) & num.notna() & den.notna()
        sel = pl[ok]
        start = pd.to_datetime(sel["shift_start"])
        frames.append(
            pd.DataFrame(
                {
                    "timestamp": start,
                    "date": start.dt.normalize(),
                    "shift": sel["shift"].astype(object),
                    "machine_id": sel["machine_id"].astype(object),
                    "kpi": kpi.name,
                    "value": (num[ok] / den[ok]).astype("float64"),
                    "_row": sel.index,
                    "_order": order,
                }
            )
        )
    if not frames:
        return _empty(), notes
    out = pd.concat(frames).sort_values(["_row", "_order"], kind="stable")
    return out[_KPI_COLS].reset_index(drop=True), notes
