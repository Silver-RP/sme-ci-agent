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
    if ((k === "start" || k === "end" || k === "change_time") && value.length > 10) value = value.slice(0, 16).replace("T", " ");
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

/**
 * Plain words for a backend error ("RuntimeError: 529 overloaded"). The raw line stays available in
 * "Chi tiết kỹ thuật"; the audience only needs to know what kind of problem it is.
 */
export function friendlyError(raw: unknown): string {
  const s = str(raw);
  if (/\b529\b|overload/i.test(s)) return t.error.kinds.overloaded;
  if (/\b429\b|rate.?limit/i.test(s)) return t.error.kinds.rateLimited;
  if (/time.?out|timed out/i.test(s)) return t.error.kinds.timeout;
  if (/connect|network|unreachable/i.test(s)) return t.error.kinds.connection;
  return t.error.kinds.other;
}

// ---------- audit_log rows (GET /audit) ----------

export type AuditTone = "ok" | "bad" | "wait" | "run" | "accent" | "neutral";
/** read = read-only tool call (many per run, hidden by default); the rest are decisions, changes, checks */
export type AuditGroup = "decision" | "change" | "check" | "read";
export type AuditIcon = "approve" | "reject" | "decide" | "answer" | "sop" | "learn" | "measure" | "halt" | "close" | "read";

export interface AuditView {
  label: string;
  detail: string;
  tone: AuditTone;
  group: AuditGroup;
  icon: AuditIcon;
}

const capitalize = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const quoted = (v: unknown) => (str(v) ? `“${str(v)}”` : "");

/** One readable line per audit row; action names follow backend/tools and backend/agent/nodes. */
export function describeAudit(action: string, params: Record<string, unknown>): AuditView {
  const p = params ?? {};
  switch (action) {
    case "approval_decided": {
      const decision = str(p.decision);
      if (decision === "sop_conflict") return { label: t.auditActions.sopConflict, detail: str(p.message), tone: "bad", group: "decision", icon: "reject" };
      const what = p.kind === "rollback" ? t.auditActions.rollback : t.auditActions.proposal;
      const tone: AuditTone = decision === "approved" ? "ok" : decision === "rejected" ? "bad" : "wait";
      const icon: AuditIcon = decision === "approved" ? "approve" : decision === "rejected" ? "reject" : "decide";
      return { label: `${capitalize(t.decisions[decision] ?? decision)} ${what}`, detail: quoted(p.reason), tone, group: "decision", icon };
    }
    case "halt_decided":
      return { label: capitalize(t.decisions[str(p.decision)] ?? str(p.decision)), detail: quoted(p.reason), tone: "wait", group: "decision", icon: "decide" };
    case "answer_received":
      return { label: t.auditActions.answer, detail: quoted(p.answer), tone: "neutral", group: "decision", icon: "answer" };
    case "run_closed":
      return { label: t.auditActions.closed, detail: quoted(p.reason), tone: "run", group: "decision", icon: "close" };
    case "halt_raised":
      return { label: t.status.halted, detail: t.halt.reasons[str(p.reason)] ?? str(p.reason), tone: "wait", group: "check", icon: "halt" };
    case "propose_sop":
      return { label: t.auditActions.proposeSop(str(p.sop_id)), detail: str(p.rationale), tone: "accent", group: "change", icon: "sop" };
    case "apply_sop":
      return { label: t.auditActions.applySop(str(p.sop_id)), detail: num(p.base_version) !== null ? t.auditActions.fromVersion(num(p.base_version)!) : "", tone: "accent", group: "change", icon: "sop" };
    case "save_learning":
      return { label: t.auditActions.learn, detail: "", tone: "ok", group: "change", icon: "learn" };
    case "measure":
      return { label: t.auditActions.measure, detail: toolArgChips(p).join(" · "), tone: "neutral", group: "check", icon: "measure" };
    case "kpi_threshold_check":
      return {
        label: p.passed === true ? t.measure.passed : t.measure.failed,
        detail: t.auditActions.threshold(kpiLabel(p.kpi), pct(p.after), pct(p.target)),
        tone: p.passed === true ? "ok" : "bad",
        group: "check",
        icon: "measure",
      };
    case "kpi_not_measured":
      return {
        label: t.auditActions.notMeasured,
        detail: p.status === "insufficient_evidence" ? t.measure.insufficient : str(p.reason),
        tone: "wait",
        group: "check",
        icon: "measure",
      };
    default:
      if (t.tools[action]) return { label: toolLabel(action), detail: toolArgChips(p).join(" · "), tone: "neutral", group: "read", icon: "read" };
      return { label: action, detail: "", tone: "neutral", group: "check", icon: "read" };
  }
}
