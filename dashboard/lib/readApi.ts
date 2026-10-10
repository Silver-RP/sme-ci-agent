// Read-only APIs behind the Runs, Overview, Kaizen and Audit screens (R10a; shapes in docs/schema/payloads.md §3).
// Fetchers are thin; the pure helpers below turn the rows into what the screens show and are unit tested.

import { getJson, type ApiOptions } from "@/lib/api";
import type { AgentEvent } from "@/lib/events";
import { isObj, num, str, type Obj } from "@/lib/format";

export interface RunSummary {
  run_id: string;
  state: "waiting" | "running" | "finished" | "error";
  started_at: string;
  finished_at: string | null;
  /** status of the last run_finished event; null while the run has not finished */
  outcome: "completed" | "closed" | "no_anomaly" | "error" | null;
  pending: { type: "answer" | "approval"; kind?: "proposal" | "rollback" | "halt"; proposal_id?: string } | null;
}

export interface AuditRow {
  id: number;
  ts: string;
  run_id: string | null;
  actor: string;
  action: string;
  params: Obj;
}

export interface SopVersion {
  version: number;
  /** "config" for the original from data/context_profile.yaml, otherwise the approver */
  created_by: string;
  run_id: string | null;
  created_at: string | null;
  content: string;
}

export interface Metric {
  /** the main KPI name from the domain config, then "mttd_mttr" and "recurrence_rate" */
  name: string;
  unit: string;
  before: number | null;
  after: number | null;
  /** false: no real source yet; before/after are null and must not be shown as numbers */
  available: boolean;
  reason: string | null;
  run_id: string | null;
}

export interface KpiSeries {
  kpi: string;
  machine: string | null;
  shift: string | null;
  points: { ts: string; value: number }[];
  /** null when no machine is chosen (several machines are averaged) */
  baseline: number | null;
  upper_limit: number | null;
  anomalies: { start: string; end: string; machine: string; shift: string }[];
}

interface RunExport {
  events: AgentEvent[];
}

const qs = (params: Record<string, string | number | null | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const listRuns = (o?: ApiOptions) => getJson<{ runs: RunSummary[] }>("/runs", o).then((d) => d.runs ?? []);

export const listAudit = (limit = 200, runId: string | null = null, o?: ApiOptions) =>
  getJson<{ rows: AuditRow[] }>(`/audit${qs({ limit, run_id: runId })}`, o).then((d) => d.rows ?? []);

export const listSopVersions = (sopId: string, o?: ApiOptions) =>
  getJson<{ versions: SopVersion[] }>(`/sop/${encodeURIComponent(sopId)}/versions`, o).then((d) => d.versions ?? []);

export const getMetrics = (o?: ApiOptions) => getJson<{ metrics: Metric[] }>("/metrics", o).then((d) => d.metrics ?? []);

export const getKpiSeries = (q: { kpi: string; machine?: string | null; shift?: string | null }, o?: ApiOptions) =>
  getJson<KpiSeries>(`/kpi/series${qs(q)}`, o);

const exportRun = (runId: string, o?: ApiOptions) => getJson<RunExport>(`/runs/${encodeURIComponent(runId)}/export`, o);

// ---------- helpers ----------

export interface Lesson {
  run_id: string;
  ts: string;
  content: Obj;
  outcome: string;
}

/** Kaizen cards of the newest completed runs. There is no lessons API, so each run's export is read. */
export async function listLessons(maxRuns = 10, o?: ApiOptions): Promise<Lesson[]> {
  const runs = (await listRuns(o)).filter((r) => r.outcome === "completed").slice(0, maxRuns);
  // one broken export must not hide the other cards
  const exports = await Promise.allSettled(runs.map((r) => exportRun(r.run_id, o)));
  return exports.flatMap((x) => (x.status === "fulfilled" ? lessonsOf(x.value.events ?? []) : []));
}

export function lessonsOf(events: AgentEvent[]): Lesson[] {
  return events
    .filter((e) => e.type === "learning_saved")
    .map((e) => {
      const content = isObj(e.payload?.content) ? e.payload.content : {};
      return { run_id: e.run_id, ts: e.ts, content, outcome: str(content.outcome) };
    });
}

/** SOP ids that appear in the log. No API lists the SOPs of the domain config, so the log is the source. */
export function sopIdsOf(rows: AuditRow[]): string[] {
  const ids = new Set<string>();
  for (const r of rows) {
    const id = str(r.params?.sop_id);
    if (id) ids.add(id);
  }
  return [...ids].sort();
}

export type VersionOrigin = { kind: "config" } | { kind: "applied" } | { kind: "restored"; from: number };

/**
 * Newest first, each with where it came from. A rollback writes a new version whose content equals an
 * earlier one, so equal content is read as "restored from" that version.
 */
export function describeVersions(versions: SopVersion[]): (SopVersion & { origin: VersionOrigin })[] {
  const oldestFirst = [...versions].sort((a, b) => a.version - b.version);
  return oldestFirst
    .map((v, i) => {
      if (v.created_by === "config") return { ...v, origin: { kind: "config" } as VersionOrigin };
      const same = oldestFirst.slice(0, i).findLast((p) => p.content === v.content);
      return { ...v, origin: same ? ({ kind: "restored", from: same.version } as VersionOrigin) : ({ kind: "applied" } as VersionOrigin) };
    })
    .reverse();
}

const DAY_MS = 86_400_000;

/** Mean of the points in the last `days` days of the series (by timestamp, not by count: a day has 1–3 points). */
export function recentMean(points: KpiSeries["points"], days: number): number | null {
  const last = points.at(-1);
  if (!last) return null;
  const from = Date.parse(last.ts) - days * DAY_MS;
  const recent = points.filter((p) => Date.parse(p.ts) > from);
  return recent.reduce((a, p) => a + p.value, 0) / recent.length;
}

/** The anomaly to open the overview on: the longest one, which is the story the demo tells (S2). */
export function focusAnomaly(anomalies: KpiSeries["anomalies"]): KpiSeries["anomalies"][number] | null {
  const length = (a: KpiSeries["anomalies"][number]) => Date.parse(a.end) - Date.parse(a.start);
  return [...anomalies].sort((a, b) => length(b) - length(a))[0] ?? null;
}

/** Relative change after vs before; null when it cannot be computed honestly. */
export function metricChange(m: Metric): number | null {
  const before = num(m.before);
  const after = num(m.after);
  if (!m.available || before === null || after === null || before === 0) return null;
  return (after - before) / before;
}
