// Placeholder data for screens whose backend API is not there yet (R10a: GET /kpi/series, /metrics, /audit,
// /sop/{id}/versions, /runs). Shapes follow docs/demo-storyboard.md §3; swap each function for an API call
// when it lands. Audit rows, SOP versions and kaizen cards are derived from the bundled recordings, so they
// are real backend output, just not live.

import type { AgentEvent } from "@/lib/events";
import { isObj, num, str, type Obj } from "@/lib/format";
import { RECORDINGS } from "@/lib/recordings";

// ---------- KPI series (S2, FR-09) ----------

export interface KpiPoint {
  ts: string; // shift start, plant local time
  value: number;
}
export interface KpiSeries {
  kpi: string;
  machine_id: string;
  shift: string | null;
  baseline: number;
  upper_limit: number;
  points: KpiPoint[];
  anomalies: { start: string; end: string }[];
  planned: { start: string; end: string }[];
}

export const MACHINES = ["M01", "M02", "M03"];
export const SHIFTS = ["morning", "afternoon", "night"];
const SHIFT_HOUR: Record<string, number> = { morning: 6, afternoon: 14, night: 22 };

// injected events of data/scenarios/scenario1.yaml (illustrative numbers)
const EFFECTS: { machine: string; start: string; end?: string; value: number; planned?: boolean }[] = [
  { machine: "M02", start: "2026-03-10T22:00:00", value: 0.062 },
  { machine: "M01", start: "2026-06-02T22:00:00", value: 0.055 },
  { machine: "M03", start: "2026-04-15T06:00:00", end: "2026-04-17T06:00:00", value: 0.045, planned: true },
];

/** Small deterministic PRNG so the mock looks the same on every render and in screenshots. */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}
function gauss(r: () => number) {
  const u = Math.max(r(), 1e-9);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}
const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:00:00`;

export function mockKpiSeries(machine: string, shift: string | null): KpiSeries {
  const baseline = 0.02;
  const sd = 0.004;
  const r = rng(machine.charCodeAt(2) * 97 + (shift ? shift.length : 0));
  const start = Date.UTC(2026, 0, 1);
  const days = 181;
  const effects = EFFECTS.filter((e) => e.machine === machine);
  const points: KpiPoint[] = [];
  for (let d = 0; d < days; d++) {
    const values: number[] = [];
    for (const s of shift ? [shift] : SHIFTS) {
      const t = new Date(start + d * 86400000 + SHIFT_HOUR[s] * 3600000);
      const ts = iso(t);
      const eff = effects.find((e) => ts >= e.start && (!e.end || ts < e.end));
      const mean = eff ? eff.value : baseline;
      values.push(Math.max(0, mean + sd * gauss(r)));
    }
    const t = new Date(start + d * 86400000 + (shift ? SHIFT_HOUR[shift] : 0) * 3600000);
    points.push({ ts: iso(t), value: values.reduce((a, b) => a + b, 0) / values.length });
  }
  const end = points.at(-1)!.ts;
  return {
    kpi: "defect_rate",
    machine_id: machine,
    shift,
    baseline,
    upper_limit: baseline + 3 * sd,
    points,
    anomalies: effects.filter((e) => !e.planned).map((e) => ({ start: e.start, end: e.end ?? end })),
    planned: effects.filter((e) => e.planned).map((e) => ({ start: e.start, end: e.end ?? end })),
  };
}

// ---------- 3 metrics (S9, FR-10): placeholders until T-042 ----------

export interface Metric {
  key: "defect" | "mttd" | "mttr" | "recurrence";
  before: number;
  after: number;
  unit: "ratio" | "hours";
  better: "lower";
}

export const MOCK_METRICS: Metric[] = [
  { key: "defect", before: 0.041, after: 0.022, unit: "ratio", better: "lower" },
  { key: "mttd", before: 72, after: 8, unit: "hours", better: "lower" },
  { key: "mttr", before: 120, after: 26, unit: "hours", better: "lower" },
  { key: "recurrence", before: 0.5, after: 0.1, unit: "ratio", better: "lower" },
];

// ---------- audit + SOP versions + kaizen (S8, S9), from the recordings ----------

export interface AuditRow {
  id: string;
  ts: string;
  run_id: string;
  who: string;
  what: string;
  kind: "decision" | "apply" | "rollback" | "answer" | "learn";
  decision?: string;
  detail: string;
}

export function auditRows(): AuditRow[] {
  const rows: AuditRow[] = [];
  for (const rec of RECORDINGS) {
    if (!rec.steps) continue; // the old events-only fixture duplicates run-happy
    for (const e of rec.events) {
      const p = e.payload ?? {};
      const base = { id: `${rec.name}:${e.event_id}`, ts: e.ts, run_id: e.run_id };
      if (e.type === "approval_decided") {
        rows.push({ ...base, who: str(p.decided_by), what: str(p.kind), kind: "decision", decision: str(p.decision), detail: str(p.reason) || str(p.change) });
      } else if (e.type === "sop_applied") {
        rows.push({ ...base, who: str(p.approved_by), what: `${str(p.sop_id)} v${str(p.version)}`, kind: "apply", detail: actionText(p.action) });
      } else if (e.type === "rollback_done" && p.rolled_back === true) {
        rows.push({ ...base, who: str(p.approved_by), what: `${str(p.sop_id)} v${str(p.version)}`, kind: "rollback", detail: `v${str(p.restored_from_version)} ← v${str(p.failed_version)}` });
      } else if (e.type === "answer_received") {
        rows.push({ ...base, who: "người vận hành", what: "answer", kind: "answer", detail: str(p.answer) });
      } else if (e.type === "learning_saved") {
        const c = isObj(p.content) ? p.content : {};
        rows.push({ ...base, who: "agent", what: "learning", kind: "learn", detail: str(c.change) });
      }
    }
  }
  return rows.sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : a.id < b.id ? 1 : -1));
}

function actionText(a: unknown): string {
  if (!isObj(a)) return "";
  return `${str(a.machine_id)}: ${str(a.parameter)} → ${str(a.value)}`;
}

export interface SopVersion {
  sop_id: string;
  version: number;
  previous: number | null;
  approved_by: string;
  kind: "apply" | "rollback";
  run_id: string;
  ts: string;
  content: string;
}

/** Versions of each SOP seen in the recordings, newest first, with the content each one carried. */
export function sopVersions(): SopVersion[] {
  const out: SopVersion[] = [];
  for (const rec of RECORDINGS) {
    if (!rec.steps) continue;
    let lastContent = "";
    for (const e of rec.events) {
      const p = e.payload ?? {};
      if (e.type === "proposal_created" && isObj(p.proposal) && isObj(p.proposal.sop_proposal)) {
        lastContent = str(p.proposal.sop_proposal.new_content);
      }
      if (e.type === "sop_applied" && num(p.version) !== null) {
        out.push({ sop_id: str(p.sop_id), version: num(p.version)!, previous: num(p.previous_version), approved_by: str(p.approved_by), kind: "apply", run_id: e.run_id, ts: e.ts, content: lastContent });
      }
      if (e.type === "rollback_done" && p.rolled_back === true && num(p.version) !== null) {
        out.push({ sop_id: str(p.sop_id), version: num(p.version)!, previous: num(p.failed_version), approved_by: str(p.approved_by), kind: "rollback", run_id: e.run_id, ts: e.ts, content: lastContent });
      }
    }
  }
  return out.sort((a, b) => b.version - a.version);
}

export interface KaizenEntry {
  run_id: string;
  ts: string;
  content: Obj;
  outcome: string;
}

export function kaizenEntries(): KaizenEntry[] {
  const out: KaizenEntry[] = [];
  for (const rec of RECORDINGS) {
    if (!rec.steps) continue;
    for (const e of rec.events as AgentEvent[]) {
      if (e.type !== "learning_saved") continue;
      const c = isObj(e.payload.content) ? e.payload.content : {};
      out.push({ run_id: e.run_id, ts: e.ts, content: c, outcome: str(c.outcome) });
    }
  }
  return out;
}

// ---------- runs list (FR-12) ----------

export interface RunRow {
  name: string;
  run_id: string;
  ts: string;
  events: number;
  result: string; // run_finished.status, or what the run waits for
}

export function runRows(): RunRow[] {
  return RECORDINGS.filter((r) => r.steps).map((r) => {
    const fin = [...r.events].reverse().find((e) => e.type === "run_finished");
    const lastStep = r.steps?.at(-1);
    const resp = isObj(lastStep?.response) ? lastStep.response : {};
    const pending = isObj(resp.pending) ? resp.pending : null;
    const result = fin ? str(fin.payload.status) : pending ? (pending.kind === "halt" ? "halt" : str(pending.type)) : str(resp.state);
    return { name: r.name, run_id: r.events[0]?.run_id ?? "", ts: r.events[0]?.ts ?? "", events: r.events.length, result };
  });
}
