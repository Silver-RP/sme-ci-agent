// Replay of a recorded run (FR-07, stage backup). A recording from scripts/export_fixtures.py has `steps`
// (each HTTP call with the run status it returned and the last event at that moment) and `events` (the
// final SSE stream). We cut the stream into one chunk per step, so the replay shows the same screens as
// a live run and waits for the presenter at every question / approval.

import type { RunStatus } from "@/lib/api";
import type { AgentEvent } from "@/lib/events";
import { isObj, str } from "@/lib/format";

export interface RecordedStep {
  request: string;
  body?: Record<string, unknown>;
  http: number;
  response: unknown;
  last_event?: unknown;
}

export interface Recording {
  name: string;
  description?: string;
  steps?: RecordedStep[];
  events: AgentEvent[];
}

export interface Chunk {
  /** events this step adds to the stream */
  events: AgentEvent[];
  /** run status after the step; null for a recording without steps */
  status: RunStatus | null;
  /** what the person did to get to the NEXT chunk (shown as a hint during replay) */
  next: { request: string; body?: Record<string, unknown> } | null;
}

function sameEvent(a: unknown, b: AgentEvent): boolean {
  return isObj(a) && a.event_id === b.event_id;
}

function asStatus(v: unknown): RunStatus | null {
  return isObj(v) && typeof v.run_id === "string" && typeof v.state === "string" ? (v as unknown as RunStatus) : null;
}

export function chunksOf(rec: Recording): Chunk[] {
  const events = rec.events;
  const steps = (rec.steps ?? []).filter((s) => s.http < 400);
  if (steps.length === 0) return [{ events: [...events], status: null, next: null }];
  const chunks: Chunk[] = [];
  let from = 0;
  steps.forEach((s, i) => {
    const next = steps[i + 1] ? { request: steps[i + 1].request, body: steps[i + 1].body } : null;
    // the stream is append-only (H-13), so each step's last event is found after the previous one
    const idx = events.findIndex((e, k) => k >= from && sameEvent(s.last_event, e));
    const end = idx >= 0 ? idx + 1 : from;
    chunks.push({ events: events.slice(from, end), status: asStatus(s.response), next });
    from = end;
  });
  if (from < events.length) chunks[chunks.length - 1].events.push(...events.slice(from));
  return chunks;
}

/** Events visible after `chunk` is fully shown, plus `cursor` events of the next one. */
export function visibleEvents(chunks: Chunk[], chunk: number, cursor: number): AgentEvent[] {
  const out: AgentEvent[] = [];
  for (let i = 0; i < chunk && i < chunks.length; i++) out.push(...chunks[i].events);
  const cur = chunks[chunk];
  if (cur) out.push(...cur.events.slice(0, cursor));
  return out;
}

/** Human hint for what the recording does next (the replay cannot take another branch). */
export function nextHint(next: Chunk["next"]): string {
  if (!next) return "";
  const b = next.body ?? {};
  if (next.request.endsWith("/answer")) return `Bản ghi trả lời: “${str(b.answer)}”`;
  if (next.request.endsWith("/retry")) return "Bản ghi bấm Thử lại";
  if (next.request.endsWith("/approval")) {
    const d = { approved: "duyệt", rejected: "từ chối", revise: "bác bỏ / bổ sung", investigate: "điều tra lại", finish: "kết thúc" }[str(b.decision)] ?? str(b.decision);
    return `Bản ghi: ${str(b.decided_by)} ${d}${str(b.reason) ? ` (“${str(b.reason)}”)` : ""}`;
  }
  return "";
}
