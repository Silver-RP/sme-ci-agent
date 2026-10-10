"use client";

import { useState } from "react";
import { Factory, Lightbulb, RotateCcw, Target, Wrench } from "lucide-react";
import { causeLabel, groupLabel, isObj, kpiLabel, num, paramLabel, pct, str, type Obj } from "@/lib/format";
import { t } from "@/lib/strings";
import { cn } from "@/lib/cn";
import { Badge, Card, CardTitle, ConfidenceBar } from "@/components/ui/primitives";
import { DecisionPanel } from "@/components/run/DecisionPanel";
import { MeasurementCard } from "@/components/run/MeasurementCard";
import { SopDiff } from "@/components/run/SopDiff";
import { TechDetail } from "@/components/run/TechDetail";
import type { DecisionInput } from "@/components/run/types";

/** Long text: 3 lines, then "Xem thêm" (FR-01.6). */
export function Clamp({ text, testId }: { text: string; testId?: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 220 || text.split("\n").length > 3;
  return (
    <div>
      <p className={cn("whitespace-pre-line leading-relaxed", !open && long && "line-clamp-3")} data-testid={testId}>
        {text}
      </p>
      {long && (
        <button className="mt-1 text-sm font-semibold text-accent hover:underline" onClick={() => setOpen(!open)}>
          {open ? t.proposal.less : t.proposal.more}
        </button>
      )}
    </div>
  );
}

/** "Máy M02 · Nhiệt độ vùng 3 → 180 °C" from proposal.action {parameter, machine_id, value}. */
export function ActionSentence({ action }: { action: Obj }) {
  const { label, unit } = paramLabel(action.parameter);
  const value = num(action.value);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-lg" data-testid="proposal-action">
      <span className="inline-flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-1 font-semibold">
        <Factory className="size-4 text-muted" />
        {t.proposal.machineAction} {str(action.machine_id)}
      </span>
      <span className="font-medium">{label}</span>
      {/* the parameter code is part of the required sentence (FR-01.1: "Máy M02: `zone3_setpoint_c` → 180") */}
      <code className="rounded bg-surface-2 px-1.5 py-0.5 text-sm text-muted" data-testid="proposal-parameter">
        {str(action.parameter)}
      </code>
      <span className="text-muted">→</span>
      <span className="rounded-lg bg-accent-soft px-3 py-0.5 text-xl font-bold tabular-nums text-accent">
        {value === null ? str(action.value) : value}
        {unit && <span className="ml-1 text-base">{unit}</span>}
      </span>
    </div>
  );
}

function ExpectedKpi({ kpi }: { kpi: Obj }) {
  const decrease = str(kpi.direction) !== "increase";
  const target = num(kpi.target);
  return (
    <p data-testid="proposal-kpi">
      <span className="font-semibold">{kpiLabel(kpi.kpi)}</span>{" "}
      <span className="text-muted">{decrease ? t.proposal.kpiDecrease : t.proposal.kpiIncrease}</span>{" "}
      <span className="font-bold text-ok">{target !== null && target <= 1 ? pct(target) : str(kpi.target)}</span>
      <span className="ml-2 text-sm text-muted">({t.proposal.target})</span>
    </p>
  );
}

/**
 * Review a proposal (S5, FR-01) or confirm a rollback (S7, FR-06): everything needed to decide on one screen.
 */
export function ProposalStage({
  pending,
  approvers,
  busy,
  lastMeasurement,
  restoreVersion = null,
  defaultApprover,
  onShowEvidence,
  onDecide,
  simulated,
}: {
  pending: Obj;
  approvers: string[];
  busy: boolean;
  lastMeasurement: Obj | null;
  /** rollback: the SOP version whose content comes back (`previous_version` of the run's sop_applied) */
  restoreVersion?: number | null;
  defaultApprover?: string;
  /** opens the agent's investigation steps (storyboard S5: evidence linked to S3) */
  onShowEvidence?: () => void;
  onDecide: (d: DecisionInput) => void;
  simulated?: boolean;
}) {
  const rollback = pending.kind === "rollback";
  const proposal = isObj(pending.proposal) ? pending.proposal : {};
  const hypothesis = isObj(proposal.hypothesis) ? proposal.hypothesis : null;
  const action = isObj(proposal.action) ? proposal.action : null;
  const sop = isObj(proposal.sop_proposal) ? proposal.sop_proposal : null;
  const current = isObj(pending.current_sop) ? pending.current_sop : null;
  const kpi = isObj(proposal.expected_kpi) ? proposal.expected_kpi : null;
  const refs = Array.isArray(proposal.evidence_refs) ? proposal.evidence_refs.map((r) => `#${str(r)}`).join(", ") : "";
  const proposalId = str(pending.proposal_id);
  const description = str(hypothesis?.description);
  const translated = causeLabel(description);
  const fromVersion = num(current?.version) ?? num(sop?.base_version);

  return (
    <div className="animate-fade-up space-y-5" data-testid="proposal-card" data-kind={rollback ? "rollback" : "proposal"}>
      <div>
        {/* the status pill next to the page title already says "waiting for you": no second badge here */}
        <h2 className="flex items-center gap-2 text-2xl font-semibold leading-tight tracking-tight" data-testid="approval-title">
          {rollback && <RotateCcw className="size-6 shrink-0 text-bad" />}
          {rollback ? t.rollback.title : t.proposal.title}
        </h2>
        {rollback && (
          <p className="mt-2 max-w-3xl text-muted" data-testid="rollback-explain">
            {t.rollback.lead}
          </p>
        )}
      </div>

      {rollback && lastMeasurement && (
        <Card className="p-5">
          <MeasurementCard m={lastMeasurement} compact />
        </Card>
      )}

      {!rollback && (
        <div className="grid gap-5 xl:grid-cols-2">
          <Card className="p-5" data-testid="block-why">
            <CardTitle icon={<Lightbulb />}>{t.proposal.why}</CardTitle>
            {hypothesis ? (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="accent" data-testid="proposal-group">
                    {groupLabel(hypothesis.group)}
                  </Badge>
                </div>
                <div>
                  <p className="text-lg font-semibold leading-snug" data-testid="proposal-hypothesis" title={translated !== description ? description : undefined}>
                    {translated}
                  </p>
                </div>
                <div>
                  <div className="mb-1 text-sm text-muted">{t.hypotheses.confidence}</div>
                  <ConfidenceBar value={num(hypothesis.confidence)} large />
                </div>
              </div>
            ) : null}
            {str(proposal.rationale) && (
              <div className="mt-4 border-t border-border pt-3 text-muted">
                <Clamp text={str(proposal.rationale)} testId="proposal-rationale" />
              </div>
            )}
            {refs && (
              <p className="mt-2 flex flex-wrap items-center gap-x-2 text-sm text-muted">
                {t.proposal.evidence(refs)}
                {onShowEvidence && (
                  <button
                    type="button"
                    className="rounded font-semibold text-accent hover:underline active:opacity-70"
                    onClick={onShowEvidence}
                    data-testid="show-evidence"
                  >
                    {t.proposal.showSteps} →
                  </button>
                )}
              </p>
            )}
          </Card>

          <Card className="p-5" data-testid="block-what">
            <CardTitle icon={<Wrench />}>{t.proposal.what}</CardTitle>
            <div className="mt-3 space-y-4">
              {action && <ActionSentence action={action} />}
              {str(proposal.change) && (
                <div className="text-muted">
                  <Clamp text={str(proposal.change)} testId="proposal-change" />
                </div>
              )}
              {kpi && (
                <div className="border-t border-border pt-3">
                  <CardTitle icon={<Target />}>{t.proposal.expect}</CardTitle>
                  <div className="mt-2">
                    <ExpectedKpi kpi={kpi} />
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {rollback && (
        <div>
          {/* built from fields: the backend's `change` is a fixed English sentence ("Roll back SOP … to version N") */}
          <p className="text-lg" data-testid="proposal-change">
            {sop ? t.rollback.sentence(str(sop.sop_id), restoreVersion) : t.rollback.sentenceNoSop}
          </p>
          {str(proposal.change) && <TechDetail className="mt-1">{str(proposal.change)}</TechDetail>}
        </div>
      )}

      {sop && (
        <Card className="p-5" data-testid="block-sop">
          <CardTitle>{t.proposal.sop}</CardTitle>
          <div className="mt-3">
            <SopDiff
              sopId={str(sop.sop_id)}
              fromVersion={fromVersion}
              toVersion={fromVersion !== null ? fromVersion + 1 : null}
              oldContent={current ? str(current.content) : null}
              newContent={str(sop.new_content)}
              fromLabel={rollback ? t.rollback.inForce : t.proposal.sopCurrent}
              toLabel={rollback ? t.rollback.restore : t.proposal.sopNew}
              toText={rollback && restoreVersion !== null ? t.rollback.restoreText(restoreVersion, fromVersion !== null ? fromVersion + 1 : null) : undefined}
            />
          </div>
        </Card>
      )}

      <DecisionPanel
        key={proposalId}
        kind={rollback ? "rollback" : "proposal"}
        proposalId={proposalId}
        approvers={approvers}
        defaultApprover={defaultApprover}
        busy={busy}
        onDecide={onDecide}
        simulated={simulated}
      />
    </div>
  );
}
