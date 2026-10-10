// One readable sentence per event for the event log (no raw JSON on the main screen, FR-02.4).

import type { AgentEvent } from "@/lib/events";
import { causeLabel, groupLabel, isObj, kpiLabel, num, paramLabel, pct, shiftLabel, shortError, str } from "@/lib/format";
import { t } from "@/lib/strings";

export function toolLabel(tool: string): string {
  return t.tools[tool] ?? tool;
}

/** Main arguments of a tool call as short "label: value" chips (machine, KPI, window, …). */
export function toolArgChips(args: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    if (v === null || v === undefined || v === "") continue;
    const label = t.toolArgs[k] ?? k;
    let value = Array.isArray(v) ? v.map(str).join(", ") : str(v);
    if (k === "kpi") value = kpiLabel(v);
    if (k === "shift") value = shiftLabel(v);
    if ((k === "start" || k === "end") && value.length > 10) value = value.slice(0, 16).replace("T", " ");
    if (value) out.push(`${label}: ${value}`);
  }
  return out;
}

export function describeEvent(e: AgentEvent): string {
  const p = e.payload ?? {};
  switch (e.type) {
    case "anomaly_detected":
      return `${kpiLabel(p.kpi)} máy ${str(p.machine)} (${shiftLabel(p.shift)}) ${pct(p.value)}, mức nền ${pct(p.baseline)}`;
    case "tool_called": {
      if (p.tool === "detect") return `${toolLabel("detect")}: ${t.activity.found(num(p.anomalies_found) ?? 0)}`;
      const args = toolArgChips(isObj(p.arguments) ? p.arguments : {});
      return `${toolLabel(str(p.tool))}${args.length ? ` (${args.join(" · ")})` : ""}${p.ok === false ? ` · ${t.activity.failed}` : ""}`;
    }
    case "hypothesis_updated": {
      const hs = (Array.isArray(p.hypotheses) ? p.hypotheses : []).filter(isObj);
      const top = [...hs].sort((a, b) => (num(b.confidence) ?? 0) - (num(a.confidence) ?? 0))[0];
      if (!top) return t.hypotheses.empty;
      return `${groupLabel(top.group)}: ${causeLabel(top.description)} (${Math.round((num(top.confidence) ?? 0) * 100)}%)${p.insufficient_evidence ? ` · ${t.hypotheses.insufficient}` : ""}`;
    }
    case "question_asked":
      if (p.kind === "halt") return `${t.status.halted}: ${t.halt.reasons[str(p.reason)] ?? str(p.reason)}`;
      return str(p.question);
    case "answer_received":
      return `“${str(p.answer)}”`;
    case "proposal_created": {
      const pr = isObj(p.proposal) ? p.proposal : {};
      const action = isObj(pr.action) ? pr.action : null;
      if (action) {
        const { label, unit } = paramLabel(action.parameter);
        return `Máy ${str(action.machine_id)}: ${label} → ${str(action.value)} ${unit}`.trim();
      }
      return str(pr.change);
    }
    case "approval_decided":
      return `${str(p.decided_by)} ${t.decisions[str(p.decision)] ?? str(p.decision)}${str(p.reason) ? `: “${str(p.reason)}”` : ""}`;
    case "sop_applied":
      return `${str(p.sop_id)} v${str(p.version)} (từ v${str(p.previous_version)}), duyệt bởi ${str(p.approved_by)}`;
    case "kpi_measured":
      if (p.status === "measured") return `${kpiLabel(p.kpi)} ${pct(p.before)} → ${pct(p.after)} · ${p.passed ? t.measure.passed : t.measure.failed}`;
      if (p.status === "insufficient_evidence") return t.measure.insufficient;
      return `${t.measure.notApplied}${str(p.reason) ? `: ${str(p.reason)}` : ""}`;
    case "rollback_done":
      return p.rolled_back ? t.audit.restored(num(p.version) ?? 0, num(p.restored_from_version) ?? 0) : "Không rollback";
    case "learning_saved": {
      const c = isObj(p.content) ? p.content : {};
      return `${t.kaizen.outcome[str(c.outcome)] ?? str(c.outcome)}: ${str(c.change)}`;
    }
    case "run_finished":
      if (p.status === "error") return `${t.status.error}: ${shortError(p.error)}`;
      return (
        { completed: t.status.completedNoLearn, closed: t.status.closed, no_anomaly: t.status.noAnomaly } as Record<string, string>
      )[str(p.status)] ?? str(p.status);
    default:
      return "";
  }
}
