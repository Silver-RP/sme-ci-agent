// Types follow docs/schema/events.json (contract backend <-> dashboard). Do not diverge.

export const EVENT_TYPES = [
  "anomaly_detected",
  "hypothesis_updated",
  "tool_called",
  "question_asked",
  "answer_received",
  "proposal_created",
  "approval_decided",
  "sop_applied",
  "kpi_measured",
  "rollback_done",
  "learning_saved",
  "run_finished",
] as const;

export const AGENTS = ["quality", "investigation", "improvement", "system"] as const;

export type EventType = (typeof EVENT_TYPES)[number];
export type AgentLabel = (typeof AGENTS)[number];

export interface AgentEvent {
  event_id: string;
  run_id: string;
  ts: string;
  type: EventType;
  agent: AgentLabel;
  domain: string;
  payload: Record<string, unknown>;
}

export interface AnomalyRow {
  eventId: string;
  ts: string;
  domain: string;
  kpi: string;
  value: number | null;
  baseline: number | null;
  machine: string;
  shift: string;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v === undefined || v === null ? "" : String(v);
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Anomaly table rows: only `anomaly_detected` events, in the given order. */
export function toAnomalyRows(events: readonly AgentEvent[]): AnomalyRow[] {
  return events
    .filter((e) => e.type === "anomaly_detected")
    .map((e) => ({
      eventId: e.event_id,
      ts: e.ts,
      domain: e.domain,
      kpi: str(e.payload.kpi),
      value: num(e.payload.value),
      baseline: num(e.payload.baseline),
      machine: str(e.payload.machine),
      shift: str(e.payload.shift),
    }));
}

/** Timeline: all events sorted by time (stable for equal timestamps). Does not mutate input. */
export function sortByTime(events: readonly AgentEvent[]): AgentEvent[] {
  return events
    .map((e, i) => ({ e, i }))
    .sort((a, b) => Date.parse(a.e.ts) - Date.parse(b.e.ts) || a.i - b.i)
    .map(({ e }) => e);
}

function short(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** One-line payload summary for the timeline. Empty payload gives an empty string. */
export function summarizePayload(payload: Record<string, unknown>, max = 140): string {
  const text = Object.entries(payload ?? {})
    .map(([k, v]) => `${k}=${short(v)}`)
    .join(", ");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
