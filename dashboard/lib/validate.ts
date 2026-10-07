import { AGENTS, EVENT_TYPES, type AgentEvent } from "@/lib/events";

export type ParseResult = { ok: true; event: AgentEvent } | { ok: false; error: string };

const REQUIRED = ["event_id", "run_id", "ts", "type", "agent", "domain", "payload"] as const;
const ALLOWED = new Set<string>(REQUIRED);

/** Runtime check mirroring docs/schema/events.json (envelope only, additionalProperties false). */
export function validateEvent(raw: unknown): ParseResult {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { ok: false, error: "event is not an object" };
  }
  const o = raw as Record<string, unknown>;
  for (const k of REQUIRED) {
    if (!(k in o)) return { ok: false, error: `missing field: ${k}` };
  }
  for (const k of Object.keys(o)) {
    if (!ALLOWED.has(k)) return { ok: false, error: `unknown field: ${k}` };
  }
  for (const k of ["event_id", "run_id", "ts", "domain"] as const) {
    if (typeof o[k] !== "string" || o[k] === "") return { ok: false, error: `invalid ${k}` };
  }
  if (Number.isNaN(Date.parse(o.ts as string))) return { ok: false, error: "invalid ts" };
  if (!(EVENT_TYPES as readonly unknown[]).includes(o.type)) {
    return { ok: false, error: `unknown type: ${String(o.type)}` };
  }
  if (!(AGENTS as readonly unknown[]).includes(o.agent)) {
    return { ok: false, error: `unknown agent: ${String(o.agent)}` };
  }
  if (typeof o.payload !== "object" || o.payload === null || Array.isArray(o.payload)) {
    return { ok: false, error: "invalid payload" };
  }
  return { ok: true, event: o as unknown as AgentEvent };
}

/** Parse an SSE `data` string, then validate. Never throws. */
export function parseEventData(data: unknown): ParseResult {
  if (typeof data !== "string") return validateEvent(data);
  try {
    return validateEvent(JSON.parse(data));
  } catch {
    return { ok: false, error: "data is not valid JSON" };
  }
}
