"""Three metrics over a replayed period, with a "no agent" control (R10b2/dev-04, closes H-11 / T-042).

    uv run python scripts/metrics_report.py --months 6 --seed 42             # scripted (fake) LLM, no key needed
    uv run python scripts/metrics_report.py --months 6 --seed 42 --llm real  # AnthropicLLM; key and model in .env

Replay (shift by shift, only data up to the shift is visible to Detect):
  with agent   Detect on the timeline -> the graph runs (Investigate .. Improve) -> a simulated person approves after
               ``approval_delay_hours`` -> data after the change (a copy, like ``post_change``) -> Measure -> Learn.
  no agent     the same anomalies are noticed ``manual_detect_delay_hours`` after they start and fixed
               ``manual_fix_delay_hours`` later; the fix brings the KPI back to its baseline.
Metrics per arm:
  defect rate before / after   pooled over units (sum of numerator / sum of denominator) in the Measure windows
                               around each fix, over all handled anomalies; ``period_rate`` = pooled over the whole
                               period after the reference days, so a later fix costs units.
  MTTD (hours)                 true start of the anomaly -> detection (the true start is the ONLY ground-truth value
                               read, and only to score; the agent never sees it)
  MTTR (hours)                 detection -> KPI back within the Measure tolerance for ``detect.rule_window`` shifts
  recurrence rate              anomalies that repeat a problem already fixed (agent: a successful lesson of the same KPI
                               is in ``learning_store``; no agent: an earlier fixed anomaly of the same KPI), counted
                               with weight ``1 - sop_prevention_efficacy`` for the agent (it versions the SOP) and
                               weight 1 without agent (nobody writes the SOP).
Assumptions (``assumptions:`` in data/context_profile.yaml; empty ``source`` = "giả định, chờ D3") are printed, and
each is varied over its ``alternatives`` in the sensitivity table. Needs Postgres (DATABASE_URL) with migrations applied;
every replay runs in its own transaction that is rolled back, so no lesson, SOP version or audit row stays behind.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from langgraph.types import Command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.agent.checkpoint import memory_checkpointer
from backend.agent.demo_llm import DemoLLM
from backend.agent.graph import build_graph
from backend.agent.lessons import pick_unhandled, relevant_lessons
from backend.agent.llm import LLM, AnthropicLLM, prepare_real_llm_env
from backend.agent.nodes.act import _sim_levels
from backend.agent.state import new_state
from backend.dataset_store import active_name, active_tables
from backend.db.config import get_database_url
from backend.detect.statistical import DetectedAnomaly, replay_detect
from backend.detect.statistical import detect as run_detect
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox import generate_dataset
from backend.sandbox.post_change import action_level, build_post_change_tables
from backend.tools.actions import measure
from backend.tools.readonly import ToolContext

NEUTRAL_ANSWER = "I have no further information about this."
MAX_STEPS = 20
TEMP_DB_MARK = "_metrics_"
MATCH_TOLERANCE = pd.Timedelta(days=3)  # a detected start this close to a true start is that anomaly
REQUIRED_ASSUMPTIONS = (
    "manual_detect_delay_hours", "manual_fix_delay_hours", "approval_delay_hours", "sop_prevention_efficacy",
)
LIMITS = [
    (
        "Recurrence compares KPI only (no cause matching); A2 repeats A1 by construction of the scenario "
        "(a very different scenario is left to R11a)."
    ),
    (
        "The fake LLM names the right cause and action; the metrics show the loop and the timing, not diagnosis "
        "quality (that is eval_rootcause.py)."
    ),
    (
        "The graph run reads the whole table (Detect's timing comes from the leak-free replay, but Investigate "
        "tools could see later rows with a real LLM)."
    ),
    "No-agent arm: delays are assumptions, and the fix is assumed to be the right one.",
]
SessionFactory = Callable[[], contextlib.AbstractContextManager[Session]]


# --- helpers -----------------------------------------------------------------------------------------------------


@contextlib.contextmanager
def replay_database(base_url: str | None = None) -> Iterator[str]:
    """An empty database (migrations applied) next to the main one, dropped at exit. A lesson is keyed by
    (kpi, machine, start) without dataset or seed, so every replay needs its own."""
    base = make_url(base_url or get_database_url())
    name = f"{base.database}{TEMP_DB_MARK}{uuid.uuid4().hex[:8]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    url = base.set(database=name).render_as_string(hide_password=False)
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(cfg, "head")
        yield url
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))  # only the one created above
        admin.dispose()


def temp_db_sessions(base_url: str | None = None) -> SessionFactory:
    """A session on a fresh empty database per use."""

    @contextlib.contextmanager
    def factory() -> Iterator[Session]:
        with replay_database(base_url) as url:
            engine = create_engine(url)
            try:
                with Session(engine) as session:
                    yield session
            finally:
                engine.dispose()

    return factory


def cut_months(tables: dict[str, pd.DataFrame], months: int) -> dict[str, pd.DataFrame]:
    """First ``months`` calendar months of the data (copies only the tables that have a time column)."""
    times = {"kpi_log": "timestamp", "machine_log": "timestamp", "production_log": "shift_start",
             "shift_schedule": "shift_start"}
    first = pd.to_datetime(tables["kpi_log"]["timestamp"]).min().normalize()
    end = first + pd.DateOffset(months=months)
    out = dict(tables)
    for name, col in times.items():
        df = tables.get(name)
        if df is not None and col in df.columns:
            out[name] = df[pd.to_datetime(df[col]) < end].reset_index(drop=True)
    return out


def true_starts(ground_truth: list[Any] | None) -> list[tuple[str, str, pd.Timestamp]]:
    """(machine, kpi, start) of the real anomalies. The ONLY place that reads ground truth, and only the start."""
    return [(g.machine_id, g.kpi, pd.Timestamp(g.start)) for g in (ground_truth or []) if not g.planned]


def match_true_start(
    anomaly_machine: str, kpi: str, detected_start: pd.Timestamp, truths: list[tuple[str, str, pd.Timestamp]],
) -> pd.Timestamp:
    """True start of the anomaly Detect found; its own start estimate when nothing matches (imported datasets)."""
    near = [
        t for m, k, t in truths if m == anomaly_machine and k == kpi and abs(t - detected_start) <= MATCH_TOLERANCE
    ]
    return min(near, key=lambda t: abs(t - detected_start)) if near else detected_start


def recovery_time(
    tables: dict[str, pd.DataFrame], config: DomainConfig, kpi: str, machine: str, after: pd.Timestamp
) -> pd.Timestamp | None:
    """End of the first ``rule_window`` consecutive shifts (from ``after``) with the KPI back within tolerance."""
    k = next(x for x in config.kpis if x.name == kpi)
    kl = tables["kpi_log"]
    sub = kl[(kl["kpi"] == kpi) & (kl["machine_id"] == machine) & (pd.to_datetime(kl["timestamp"]) >= after)]
    sub = sub.assign(timestamp=pd.to_datetime(sub["timestamp"])).sort_values("timestamp")
    tol = config.measure.tolerance
    ok = (sub["value"] <= k.target * (1 + tol)) if k.direction == "decrease" else (sub["value"] >= k.target * (1 - tol))
    run = 0
    for ts, good in zip(sub["timestamp"], ok.tolist(), strict=True):
        run = run + 1 if good else 0
        if run >= config.detect.rule_window:
            return pd.Timestamp(ts)
    return None


# --- one handled anomaly -----------------------------------------------------------------------------------------


@dataclass
class Handled:
    kpi: str
    machine: str
    true_start: pd.Timestamp
    detected_at: pd.Timestamp
    change_time: pd.Timestamp | None
    resolved_at: pd.Timestamp | None = None
    before: float | None = None
    after: float | None = None
    n_before: int = 0
    n_after: int = 0
    repeat: bool = False  # the same problem came back after it was fixed (weights: see module doc)
    passed: bool | None = None
    note: str = ""

    @property
    def mttd_hours(self) -> float:
        return (self.detected_at - self.true_start) / pd.Timedelta(hours=1)

    @property
    def mttr_hours(self) -> float | None:
        return None if self.resolved_at is None else (self.resolved_at - self.detected_at) / pd.Timedelta(hours=1)


def _score(
    ctx_base: ToolContext, post: dict[str, pd.DataFrame], h: Handled, config: DomainConfig
) -> None:
    """Fill before/after/resolved of ``h`` from the data after its change, using the Measure tool (pooled)."""
    if h.change_time is None:
        return
    h.resolved_at = recovery_time(post, config, h.kpi, h.machine, h.change_time)
    res = measure(
        ToolContext(tables=post, session=ctx_base.session, config=config, run_id=ctx_base.run_id),
        kpi=h.kpi, change_time=h.change_time.isoformat(), window_days=config.measure.window_days,
        machine_id=h.machine, min_units_after=config.measure.min_units_after,
    )
    h.before, h.after, h.n_before, h.n_after = res["before"], res["after"], res["n_before"], res["n_after"]


def _drive(graph: Any, state: Any, cfg: dict, session: Session, approver: str) -> dict[str, Any]:
    """Play the people in the loop until the graph ends; returns the final state values."""
    payload: object = state
    for _ in range(MAX_STEPS):
        graph.invoke(payload, cfg)
        session.commit()
        snap = graph.get_state(cfg)
        if not snap.next:
            return dict(snap.values)
        step = snap.next[0]
        if step == "wait_answer":
            payload = Command(resume=NEUTRAL_ANSWER)
        elif step == "wait_halt":
            payload = Command(resume={"decision": "finish", "decided_by": approver, "reason": "metrics replay"})
        elif step == "wait_rollback":
            payload = Command(resume={"decision": "rejected", "decided_by": approver, "reason": "metrics replay: keep"})
        else:  # wait_approval (and the "wait for more data" question of Measure)
            payload = Command(resume={"decision": "approved", "decided_by": approver, "reason": "metrics replay"})
    raise RuntimeError(f"run did not finish within {MAX_STEPS} steps")


# --- the two arms ------------------------------------------------------------------------------------------------


@dataclass
class Arm:
    handled: list[Handled] = field(default_factory=list)
    final_tables: dict[str, pd.DataFrame] | None = None


class Evaluator:
    """Replays one dataset. The leak-free Detect replay is computed once; each arm is cached by the assumptions it uses."""

    def __init__(
        self,
        config: DomainConfig,
        tables: dict[str, pd.DataFrame],
        ground_truth: list[Any] | None,
        sessions: SessionFactory,
        *,
        seed: int = 42,
        llm_factory: Callable[[str], LLM] | None = None,
        replay: list[DetectedAnomaly] | None = None,  # a replay already computed on the same tables (~7 s per 6 months)
    ) -> None:
        missing = [n for n in REQUIRED_ASSUMPTIONS if n not in config.assumptions]
        if missing:
            raise ValueError(f"the domain config has no assumptions: {', '.join(missing)}")
        self.config, self.tables, self.sessions, self.seed = config, tables, sessions, seed
        self.truths = true_starts(ground_truth)
        self.llm_factory = llm_factory or (lambda machine: DemoLLM(config, ask_first=False, machine_id=machine))
        self.replay = replay if replay is not None else replay_detect(tables, config)
        self._agent: dict[tuple, Arm] = {}
        self._manual: dict[tuple, Arm] = {}

    # -- shared

    def _levels(self, kpi: str) -> tuple[float, float]:
        return _sim_levels(kpi, self.config)

    def _post(self, base: dict[str, pd.DataFrame], h: Handled, run_id: str, action: dict | None) -> dict[str, pd.DataFrame]:
        baseline, noise = self._levels(h.kpi)
        level = action_level(action, h.machine, baseline) if action is not None else None
        return build_post_change_tables(
            base, kpi=h.kpi, change_time=h.change_time, machine_id=h.machine, fixed=action is None, level=level,
            baseline=baseline, noise_sd=noise, window_days=self.config.measure.window_days,
            anomaly_start=h.true_start, run_id=run_id, seed=self.seed, config=self.config,
        )

    # -- with agent

    def agent_arm(self, approval_delay_hours: float) -> Arm:
        key = (approval_delay_hours,)
        if key not in self._agent:
            self._agent[key] = self._run_agent_arm(approval_delay_hours)
        return self._agent[key]

    def _run_agent_arm(self, approval_delay_hours: float) -> Arm:
        config = self.config
        by_key = {(d.anomaly.kpi, d.anomaly.machine_id, d.anomaly.start): d for d in self.replay}
        arm = Arm()
        chain = self.tables
        prev_skip = os.environ.get("SME_SKIP_HANDLED")
        os.environ["SME_SKIP_HANDLED"] = "1"  # the run picks the anomaly that has no lesson yet
        try:
            with self.sessions() as session:  # one own transaction for the whole replay of this arm
                for i in range(len(self.replay) + 1):
                    run_id = f"replay_{self.seed}_{i}"
                    ctx = ToolContext(tables=self.tables, session=session, config=config, run_id=run_id)
                    found = run_detect(self.tables, config, run_id=run_id)
                    first = pick_unhandled(found, ctx)
                    if first is None:
                        break
                    det = by_key.get((first["kpi"], first["machine"], pd.Timestamp(first["start"])))
                    if det is None:  # not seen by the replay: no detection time, so it cannot be scored
                        break
                    repeat = any(
                        x.get("outcome") == "success" for x in relevant_lessons(ctx, first, 1000)
                    )
                    h = Handled(
                        kpi=first["kpi"], machine=first["machine"],
                        true_start=match_true_start(first["machine"], first["kpi"], det.anomaly.start, self.truths),
                        detected_at=det.detected_at,
                        change_time=det.detected_at + pd.Timedelta(hours=approval_delay_hours), repeat=repeat,
                    )
                    state = new_state(run_id, config.domain)
                    state["change_time"] = h.change_time.isoformat()
                    graph = build_graph(
                        config, checkpointer=memory_checkpointer(), llm=self.llm_factory(h.machine), tool_ctx=ctx,
                        full_loop=True,
                    )
                    values = _drive(graph, state, {"configurable": {"thread_id": run_id}}, session, config.approvers[0])
                    applied = values.get("applied") or {}
                    h.passed = (values.get("measurement") or {}).get("passed")
                    if applied.get("action"):
                        post = self._post(self.tables, h, run_id, applied["action"])
                        _score(ctx, post, h, config)
                        chain = self._post(chain, h, run_id, applied["action"])
                    else:
                        h.note = "no change applied"
                    arm.handled.append(h)
        finally:
            if prev_skip is None:
                os.environ.pop("SME_SKIP_HANDLED", None)
            else:
                os.environ["SME_SKIP_HANDLED"] = prev_skip
        arm.final_tables = chain
        return arm

    # -- no agent

    def manual_arm(self, detect_delay_hours: float, fix_delay_hours: float) -> Arm:
        key = (detect_delay_hours, fix_delay_hours)
        if key not in self._manual:
            self._manual[key] = self._run_manual_arm(detect_delay_hours, fix_delay_hours)
        return self._manual[key]

    def _run_manual_arm(self, detect_delay_hours: float, fix_delay_hours: float) -> Arm:
        config = self.config
        arm = Arm()
        chain = self.tables
        last = pd.to_datetime(self.tables["kpi_log"]["timestamp"]).max()
        with self.sessions() as session:
            for i, d in enumerate(self.replay):
                true_start = match_true_start(d.anomaly.machine_id, d.anomaly.kpi, d.anomaly.start, self.truths)
                detected = true_start + pd.Timedelta(hours=detect_delay_hours)
                fix = detected + pd.Timedelta(hours=fix_delay_hours)
                h = Handled(kpi=d.anomaly.kpi, machine=d.anomaly.machine_id, true_start=true_start,
                            detected_at=detected, change_time=fix)
                h.repeat = any(
                    x.kpi == h.kpi and x.change_time is not None and x.change_time <= true_start for x in arm.handled
                )
                if fix > last:
                    h.change_time, h.note = None, "fix after the end of the data"
                    arm.handled.append(h)
                    continue
                run_id = f"manual_{self.seed}_{i}"
                ctx = ToolContext(tables=self.tables, session=session, config=config, run_id=run_id)
                post = self._post(self.tables, h, run_id, None)
                _score(ctx, post, h, config)
                chain = self._post(chain, h, run_id, None)
                arm.handled.append(h)
        arm.final_tables = chain
        return arm

    # -- summaries

    def period_rate(self, arm: Arm) -> float | None:
        """Pooled KPI over the whole period after the reference days (first KPI of the config)."""
        k = self.config.kpis[0]
        pl = (arm.final_tables or self.tables).get("production_log")
        if pl is None or pl.empty:
            return None
        start = pd.to_datetime(self.tables["kpi_log"]["timestamp"]).min().normalize() + pd.Timedelta(
            days=self.config.detect.reference_days)
        p = pl[pd.to_datetime(pl["shift_start"]) >= start]
        den = float(p[k.denominator].sum())
        return float(p[k.numerator].sum()) / den if den > 0 else None

    def summarize(self, arm: Arm, prevention: float) -> dict[str, Any]:
        hs = arm.handled
        n_b = sum(h.n_before for h in hs if h.before is not None)
        n_a = sum(h.n_after for h in hs if h.after is not None)
        mttr = [h.mttr_hours for h in hs if h.mttr_hours is not None]
        return {
            "anomalies_handled": len(hs),
            "defect_rate_before": sum(h.before * h.n_before for h in hs if h.before is not None) / n_b if n_b else None,
            "defect_rate_after": sum(h.after * h.n_after for h in hs if h.after is not None) / n_a if n_a else None,
            "period_rate": self.period_rate(arm),
            "mttd_hours": sum(h.mttd_hours for h in hs) / len(hs) if hs else None,
            "mttr_hours": sum(mttr) / len(mttr) if mttr else None,
            "recurrence_rate": sum((1 - prevention) for h in hs if h.repeat) / len(hs) if hs else None,
            "events": [
                {"kpi": h.kpi, "machine": h.machine, "true_start": h.true_start.isoformat(),
                 "detected_at": h.detected_at.isoformat(),
                 "change_time": h.change_time.isoformat() if h.change_time is not None else None,
                 "resolved_at": h.resolved_at.isoformat() if h.resolved_at is not None else None,
                 "before": h.before, "after": h.after, "repeat": h.repeat, "passed": h.passed, "note": h.note}
                for h in hs
            ],
        }

    def metrics(self, a: dict[str, float]) -> dict[str, Any]:
        """Both arms for assumption values ``a`` (name -> value)."""
        agent = self.agent_arm(a["approval_delay_hours"])
        manual = self.manual_arm(a["manual_detect_delay_hours"], a["manual_fix_delay_hours"])
        return {
            "agent": self.summarize(agent, a["sop_prevention_efficacy"]),
            "manual": self.summarize(manual, 0.0),
        }

    def assumption_values(self, override: dict[str, float] | None = None) -> dict[str, float]:
        vals = {n: x.value for n, x in self.config.assumptions.items()}
        vals.update(override or {})
        return vals


# --- report ------------------------------------------------------------------------------------------------------

HEADLINE = ("defect_rate_before", "defect_rate_after", "period_rate", "mttd_hours", "mttr_hours", "recurrence_rate")


def build_report(
    ev: Evaluator, *, dataset: str, months: int, llm: str, sensitivity: bool = True
) -> dict[str, Any]:
    base = ev.metrics(ev.assumption_values())
    rows = []
    if sensitivity:
        for name, a in ev.config.assumptions.items():
            for alt in a.alternatives:
                m = ev.metrics(ev.assumption_values({name: alt}))
                rows.append({
                    "assumption": name, "value": alt,
                    "agent": {k: m["agent"][k] for k in HEADLINE}, "manual": {k: m["manual"][k] for k in HEADLINE},
                })
    return {
        "dataset": dataset,
        "seed": ev.seed,
        "months": months,
        "llm": llm,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "assumptions": [
            {"name": n, "value": a.value, "unit": a.unit, "source": a.source_label}
            for n, a in ev.config.assumptions.items()
        ],
        "agent": base["agent"],
        "manual": base["manual"],
        "sensitivity": rows,
        "limits": LIMITS,
    }


def _f(v: Any) -> str:
    return "n/a" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))


def to_markdown(rep: dict[str, Any]) -> str:
    out = [f"# Metrics report: dataset {rep['dataset']}, seed {rep['seed']}, {rep['months']} months, LLM {rep['llm']}",
           f"Generated at {rep['generated_at']}", "", "## Metrics", "",
           "| metric | with agent | no agent |", "|---|---|---|"]
    out += [f"| {k} | {_f(rep['agent'][k])} | {_f(rep['manual'][k])} |" for k in ("anomalies_handled", *HEADLINE)]
    out += ["", "## Assumptions", "", "| name | value | unit | source |", "|---|---|---|---|"]
    out += [f"| {a['name']} | {a['value']} | {a['unit']} | {a['source']} |" for a in rep["assumptions"]]
    head = (
        "| assumption | value | agent mttd | agent mttr | agent period_rate | agent recurrence | "
        "manual mttd | manual mttr | manual period_rate |"
    )
    out += ["", "## Sensitivity (one assumption changed at a time)", "", head, "|---|---|---|---|---|---|---|---|---|"]
    for r in rep["sensitivity"]:
        a, m = r["agent"], r["manual"]
        out.append(
            f"| {r['assumption']} | {r['value']} | {_f(a['mttd_hours'])} | {_f(a['mttr_hours'])} | "
            f"{_f(a['period_rate'])} | {_f(a['recurrence_rate'])} | {_f(m['mttd_hours'])} | {_f(m['mttr_hours'])} | "
            f"{_f(m['period_rate'])} |"
        )
    out += ["", "## Limits", ""] + [f"- {x}" for x in rep["limits"]]
    return "\n".join(out) + "\n"


def report_paths(out_dir: Path, dataset: str, seed: int) -> tuple[Path, Path]:
    stem = f"metrics_{dataset}_seed{seed}"
    return out_dir / f"{stem}.json", out_dir / f"{stem}.md"


def write_report(rep: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, mp = report_paths(out_dir, rep["dataset"], rep["seed"])
    jp.write_text(json.dumps(rep, indent=2, sort_keys=True, default=str), encoding="utf-8")
    mp.write_text(to_markdown(rep), encoding="utf-8")
    return jp, mp


DEFAULT_OUT_DIR = ROOT / "data" / "reports"


def load_inputs(seed: int, months: int) -> tuple[dict[str, pd.DataFrame], list[Any] | None, str]:
    """Tables (simulator, or the dataset in SME_DATASET), ground truth for scoring (simulator only), dataset name."""
    name = active_name()
    data = generate_dataset(seed=seed) if name is None else None
    tables = active_tables(lambda: data.tables)  # type: ignore[union-attr]
    return cut_months(tables, months), (data.ground_truth if data is not None else None), name or "sandbox"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--months", type=int, default=6)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--llm", choices=["scripted", "real"], default="scripted")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--no-sensitivity", action="store_true", help="skip the sensitivity table")
    args = p.parse_args(argv)
    if args.months < 1:
        print("--months must be at least 1", file=sys.stderr)
        return 2
    if args.llm == "real":
        problem = prepare_real_llm_env(ROOT / ".env")
        if problem:
            print(problem, file=sys.stderr)
            return 2
    config = load_domain_config()
    tables, truth, dataset = load_inputs(args.seed, args.months)
    factory = (lambda _m: AnthropicLLM()) if args.llm == "real" else None
    ev = Evaluator(config, tables, truth, temp_db_sessions(), seed=args.seed, llm_factory=factory)
    rep = build_report(ev, dataset=dataset, months=args.months, llm=args.llm, sensitivity=not args.no_sensitivity)
    jp, mp = write_report(rep, args.out_dir)
    print(to_markdown(rep))
    print(f"written: {jp} , {mp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
