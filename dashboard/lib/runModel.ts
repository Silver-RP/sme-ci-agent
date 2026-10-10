// Pure view model of a run: what the screens show, derived from the event stream and the run status.
// No React here so every rule is unit-tested against the real fixtures in docs/schema/examples/.

import type { AgentEvent } from "@/lib/events";
import { isObj, num, str, type Obj } from "@/lib/format";
import type { RunStatus } from "@/lib/api";

/** The 8 steps of the loop (FR-08). Rollback is a branch, shown only once it happens. */
export const STEPS = ["detect", "investigate", "ask", "improve", "act", "measure", "learn", "rollback"] as const;
export type StepKey = (typeof STEPS)[number];
export const MAIN_STEPS: readonly StepKey[] = STEPS.slice(0, 7);

/** Event -> step of the loop. One table, so the stepper and the log agree. */
export function stepOfEvent(e: AgentEvent): StepKey | null {
  const p = e.payload ?? {};
  switch (e.type) {
    case "anomaly_detected":
      return "detect";
    case "tool_called":
      return p.tool === "detect" ? "detect" : "investigate";
    case "hypothesis_updated":
      return "investigate";
    case "question_asked":
      return p.kind === "halt" ? null : "ask";
    case "answer_received":
      return "ask";
    case "proposal_created":
      return isObj(p.proposal) && p.proposal.kind === "rollback" ? "rollback" : "improve";
    case "approval_decided":
      if (p.kind === "rollback") return "rollback";
      if (p.kind === "proposal") return p.decision === "approved" ? "act" : "improve";
      return null;
    case "sop_applied":
      return "act";
    case "kpi_measured":
      return "measure";
    case "rollback_done":
      return "rollback";
    case "learning_saved":
      return "learn";
    default:
      return null;
  }
}

export interface ToolCall {
  id: string;
  ts: string;
  tool: string;
  args: Obj;
  ok: boolean | null;
  found: number | null; // detect only
}

export interface HypothesisView {
  group: string;
  description: string;
  confidence: number | null;
}

/** What the main "stage" shows right now. */
export type Phase =
  | "start"
  | "thinking"
  | "answer"
  | "evidence"
  | "proposal"
  | "rollback"
  | "halt"
  | "error"
  | "completed"
  | "closed"
  | "no_anomaly"
  | "finished";

export interface RunModel {
  anomaly: Obj | null;
  tools: ToolCall[];
  hypotheses: HypothesisView[];
  insufficient: boolean;
  question: { attempt: number | null; max: number | null } | null;
  measurements: Obj[];
  lastMeasurement: Obj | null;
  learning: Obj | null;
  applied: Obj[];
  finished: Obj | null;
  reached: StepKey[];
  current: StepKey | null;
  rolledBack: boolean;
  /** the latest question came from Measure (too few points after the change), not from Investigate */
  evidenceAsk: boolean;
  /**
   * The last decision could not be carried out because another run changed the SOP meanwhile (H-14, R10c):
   * an approval with decision "sop_conflict" or a rollback_done with `conflict`. Cleared by the next normal
   * decision, SOP version or successful rollback.
   */
  conflict: { kind: "approval" | "rollback"; sopId: string; currentVersion: number | null; message: string } | null;
}

export function buildRunModel(events: readonly AgentEvent[]): RunModel {
  let anomaly: Obj | null = null;
  const tools: ToolCall[] = [];
  let hypotheses: HypothesisView[] = [];
  let insufficient = false;
  let question: RunModel["question"] = null;
  const measurements: Obj[] = [];
  let learning: Obj | null = null;
  const applied: Obj[] = [];
  let finished: Obj | null = null;
  const reached: StepKey[] = [];
  let current: StepKey | null = null;
  let rolledBack = false;
  let evidenceAsk = false;
  let conflict: RunModel["conflict"] = null;

  for (const e of events) {
    const p = e.payload ?? {};
    let step = stepOfEvent(e);
    if (e.type === "question_asked" && step === "ask") {
      evidenceAsk = current === "measure" && measurements.at(-1)?.status === "insufficient_evidence";
      if (evidenceAsk) step = "measure";
    } else if (e.type === "answer_received" && evidenceAsk) {
      step = "measure";
    }
    if (step) {
      current = step;
      if (!reached.includes(step)) reached.push(step);
    }
    switch (e.type) {
      case "anomaly_detected":
        anomaly = p;
        break;
      case "tool_called":
        tools.push({
          id: e.event_id,
          ts: e.ts,
          tool: str(p.tool) || "?",
          args: isObj(p.arguments) ? p.arguments : {},
          ok: typeof p.ok === "boolean" ? p.ok : p.tool === "detect" ? true : null,
          found: num(p.anomalies_found),
        });
        break;
      case "hypothesis_updated":
        hypotheses = (Array.isArray(p.hypotheses) ? p.hypotheses : []).filter(isObj).map((h) => ({
          group: str(h.group),
          description: str(h.description),
          confidence: num(h.confidence),
        }));
        hypotheses.sort((a, b) => (b.confidence ?? -1) - (a.confidence ?? -1));
        insufficient = p.insufficient_evidence === true;
        break;
      case "question_asked":
        if (p.kind !== "halt") question = { attempt: num(p.attempt), max: num(p.max_questions) };
        break;
      case "kpi_measured":
        measurements.push(p);
        break;
      case "sop_applied":
        applied.push(p);
        conflict = null;
        break;
      case "approval_decided":
        conflict =
          p.decision === "sop_conflict"
            ? { kind: "approval", sopId: str(p.sop_id), currentVersion: num(p.current_version), message: str(p.message) }
            : null;
        break;
      case "rollback_done":
        if (p.rolled_back === true) rolledBack = true;
        conflict = str(p.conflict)
          ? { kind: "rollback", sopId: str(p.sop_id), currentVersion: num(p.current_version), message: str(p.conflict) }
          : null;
        break;
      case "learning_saved":
        learning = p;
        break;
      case "run_finished":
        finished = p;
        break;
    }
    // the error before a Retry stays in the stream (H-13): any later event means the run went on
    if (e.type !== "run_finished") finished = null;
  }
  return {
    anomaly,
    tools,
    hypotheses,
    insufficient,
    question,
    measurements,
    lastMeasurement: measurements.at(-1) ?? null,
    learning,
    applied,
    finished,
    reached,
    current,
    rolledBack,
    evidenceAsk,
    conflict,
  };
}

/** Status of the stage: pending interrupt first, then the error, then how the run ended (H-24). */
export function phaseOf(status: RunStatus | null, model: RunModel, opts: { started: boolean; busy: boolean }): Phase {
  if (opts.busy) return "thinking";
  if (status?.state === "error") return "error";
  const pending = status?.pending;
  if (pending?.type === "answer") return model.evidenceAsk ? "evidence" : "answer";
  if (pending?.type === "approval") {
    if (pending.kind === "rollback") return "rollback";
    if (pending.kind === "halt") return "halt";
    return "proposal";
  }
  const fin = model.finished;
  if (fin) {
    if (fin.status === "error") return "error";
    if (fin.status === "completed") return "completed";
    if (fin.status === "closed") return "closed";
    if (fin.status === "no_anomaly") return "no_anomaly";
    return "finished";
  }
  if (status?.state === "finished") {
    if (status.status === "completed") return "completed";
    if (status.status === "closed") return "closed";
    if (status.status === "no_anomaly") return "no_anomaly";
    return "finished";
  }
  if (!opts.started && !status) return "start";
  return "thinking";
}

/** Step to highlight: a pending interrupt says where the run is waiting. */
export function activeStep(phase: Phase, model: RunModel): StepKey | null {
  switch (phase) {
    case "answer":
      return "ask";
    case "evidence":
      return "measure";
    case "proposal":
      return "improve";
    case "rollback":
      return "rollback";
    case "completed":
    case "start":
    case "halt":
    case "error":
    case "closed":
    case "no_anomaly":
    case "finished":
      return null; // nothing is running: no step glows
    case "thinking":
      return model.current ?? "detect";
    default:
      return model.current;
  }
}

export type StepState = "done" | "active" | "todo";

export function stepStates(phase: Phase, model: RunModel): Record<StepKey, StepState> {
  const active = activeStep(phase, model);
  const out = {} as Record<StepKey, StepState>;
  for (const s of STEPS) {
    if (phase === "completed") out[s] = model.reached.includes(s) ? "done" : "todo";
    else if (s === active) out[s] = "active";
    else out[s] = model.reached.includes(s) ? "done" : "todo";
  }
  return out;
}
