"""Named datasets imported from CSV (docs/schema/data_contract.md section 3).

A dataset is a directory ``<root>/<name>/`` holding the contract CSV files as imported plus the marker file
``_COMPLETE``. ``save_dataset`` writes into a temporary directory next to the target and renames it once, so a
process killed half way leaves no loadable dataset. ``SME_DATASET=<name>`` makes the app and the tools read the
tables and the base SOP of that dataset instead of the simulator and the SOP of the domain config.

Tables of the dataset are typed like the simulator tables (``TABLE_SCHEMAS``); ``kpi_log`` is derived
(contract 2.8), never stored.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from backend.sandbox.schema import TABLE_SCHEMAS

if TYPE_CHECKING:
    from backend.domain_config import DomainConfig

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "data" / "datasets"
ENV_NAME = "SME_DATASET"
ENV_ROOT = "SME_DATASETS_DIR"
MARKER = "_COMPLETE"
IMPORT_ORIGIN = "import"  # created_by of the base SOP versions of a dataset
SOURCE_TABLES: tuple[str, ...] = ("production_log", "machine_log", "shift_schedule", "material_batches", "sop")
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class DatasetError(RuntimeError):
    """A dataset cannot be saved or loaded."""


def datasets_root() -> Path:
    env = os.environ.get(ENV_ROOT, "").strip()
    return Path(env) if env else DEFAULT_ROOT


def active_name() -> str | None:
    """Name in ``SME_DATASET`` (None when unset or blank: simulator data)."""
    return os.environ.get(ENV_NAME, "").strip() or None


def check_name(name: str) -> str:
    if not NAME_RE.fullmatch(name):
        raise DatasetError(f"invalid dataset name {name!r}: use letters, digits, '_' or '-' (max 64 characters)")
    return name


def dataset_path(name: str) -> Path:
    return datasets_root() / check_name(name)


def save_dataset(src: str | Path, name: str, row_counts: dict[str, int] | None = None) -> Path:
    """Copy the contract files of ``src`` (bytes as they are) into a new dataset. The source is not touched.

    Writes to a temporary directory, adds the marker, then renames it to the final name in one step."""
    check_name(name)
    src = Path(src)
    root = datasets_root()
    final = root / name
    if final.exists():
        raise DatasetError(f"dataset {name!r} already exists at {final}; pick another --name")
    root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{name}.tmp-", dir=root))
    try:
        copied = []
        for t in SOURCE_TABLES:
            f = src / f"{t}.csv"
            if f.is_file():
                shutil.copyfile(f, tmp / f.name)
                copied.append(t)
        (tmp / MARKER).write_text(
            json.dumps({"name": name, "tables": copied, "rows": row_counts or {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.rename(final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def _bool(v) -> bool:
    return str(v).strip().lower() == "true"


def _typed(table: str, df: pd.DataFrame) -> pd.DataFrame:
    schema = TABLE_SCHEMAS[table]
    out = df.reindex(columns=list(schema))
    for col, kind in schema.items():
        s = out[col]
        if kind == "datetime":
            out[col] = pd.to_datetime(s, errors="coerce").astype("datetime64[ns]")
        elif kind == "int":
            n = pd.to_numeric(s, errors="coerce")
            out[col] = n.astype("int64") if n.notna().all() else n.astype("float64")  # blank optional cell: NaN
        elif kind == "float":
            out[col] = pd.to_numeric(s, errors="coerce").astype("float64")
        elif kind == "bool":
            out[col] = s.map(_bool).astype(bool) if len(s) else s.astype(bool)
        else:
            out[col] = s.astype(object).where(s.notna(), None)
    return out.reset_index(drop=True)


def _read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False, skip_blank_lines=True)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda col: col.str.strip())
    return df.replace("", pd.NA)


def _complete_dir(name: str) -> Path:
    path = dataset_path(name)
    if not path.is_dir():
        raise DatasetError(f"{ENV_NAME}={name!r}: dataset not found at {path} (import it with scripts/import_data.py)")
    if not (path / MARKER).is_file():
        raise DatasetError(
            f"{ENV_NAME}={name!r}: dataset at {path} is incomplete (no {MARKER} marker; the import was interrupted). "
            "Import it again."
        )
    return path


def load_tables(name: str, cfg: DomainConfig | None = None) -> dict[str, pd.DataFrame]:
    """Tables of a dataset with the simulator's table set and types (``kpi_log`` derived from ``production_log``)."""
    from backend.domain_config import load_domain_config
    from backend.sandbox.kpi_derive import derive_kpi_log

    path = _complete_dir(name)
    cfg = cfg or load_domain_config()
    raw = {t: _read_csv(path / f"{t}.csv") for t in SOURCE_TABLES if (path / f"{t}.csv").is_file()}
    out: dict[str, pd.DataFrame] = {}
    for table in TABLE_SCHEMAS:
        if table == "kpi_log":
            continue
        out[table] = _typed(table, raw.get(table, pd.DataFrame()))
    pl = raw.get("production_log", pd.DataFrame(columns=["shift_start"]))
    kpi, _notes = derive_kpi_log(pl, cfg)  # file order, as the validator saw it
    out["kpi_log"] = _typed("kpi_log", kpi)
    return {t: out[t] for t in TABLE_SCHEMAS}


def load_sop(name: str):
    """Base SOP versions of a dataset from its ``sop.csv`` (``origin`` = ``import``)."""
    from backend.domain_config import SOP

    path = _complete_dir(name) / "sop.csv"
    if not path.is_file():
        return []
    df = _read_csv(path)
    out = []
    for (sop_id, version), g in df.groupby(["sop_id", "version"], sort=False):
        g = g.assign(_n=pd.to_numeric(g["step_no"])).sort_values("_n", kind="stable")
        out.append(
            SOP(id=sop_id, version=int(version), title=str(g["title"].iloc[0]),
                steps=[str(t) for t in g["step_text"]], origin=IMPORT_ORIGIN)
        )
    return out


def apply_to_config(cfg: DomainConfig) -> DomainConfig:
    """With ``SME_DATASET`` set: the same config with ``sop`` from the dataset (config-only SOPs are dropped)."""
    name = active_name()
    if name is None:
        return cfg
    return cfg.model_copy(update={"sop": load_sop(name)})


_cache: dict[tuple, dict[str, pd.DataFrame]] = {}


def active_tables(fallback):
    """Tables of the dataset in ``SME_DATASET``; ``fallback()`` (simulator) when it is unset."""
    name = active_name()
    if name is None:
        return fallback()
    marker = _complete_dir(name) / MARKER
    key = (name, str(marker), marker.stat().st_mtime_ns)
    if key not in _cache:
        _cache[key] = load_tables(name)
    return _cache[key]
