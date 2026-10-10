"use client";

import { useState } from "react";
import { Check, Lock, MessageSquareWarning, RotateCcw, Search, ShieldCheck, Square, X } from "lucide-react";
import type { Decision } from "@/lib/api";
import { t } from "@/lib/strings";
import { Button, Input, Label, Select, Spinner, Textarea } from "@/components/ui/primitives";
import type { DecisionInput } from "@/components/run/types";

type Choice = {
  decision: Decision["decision"];
  label: string;
  variant: "solid" | "outline" | "danger" | "ok";
  icon: React.ReactNode;
  needsReason?: boolean;
};

function choicesFor(kind: Decision["kind"], options: string[]): Choice[] {
  if (kind === "halt") {
    const all: Choice[] = [
      { decision: "investigate", label: t.decision.investigate, variant: "solid", icon: <Search className="size-5" /> },
      { decision: "finish", label: t.decision.finish, variant: "outline", icon: <Square className="size-4" /> },
    ];
    // the backend says which choices this halt allows (e.g. only "finish" after the total rollback limit)
    return options.length > 0 ? all.filter((c) => options.includes(c.decision)) : all;
  }
  if (kind === "rollback") {
    return [
      { decision: "approved", label: t.decision.approveRollback, variant: "danger", icon: <RotateCcw className="size-5" /> },
      { decision: "rejected", label: t.decision.rejectRollback, variant: "outline", icon: <ShieldCheck className="size-5" /> },
    ];
  }
  return [
    { decision: "approved", label: t.decision.approve, variant: "ok", icon: <Check className="size-5" /> },
    { decision: "rejected", label: t.decision.reject, variant: "outline", icon: <X className="size-5" /> },
    { decision: "revise", label: t.decision.revise, variant: "outline", icon: <MessageSquareWarning className="size-5" />, needsReason: true },
  ];
}

/**
 * Approver + reason + the buttons for one pending approval. Nothing is sent without a click by a person;
 * buttons stay locked until an approver from the allow-list is chosen (FR-01.3) and while a request runs.
 * Remount it (key = proposal_id) when the pending approval changes, so a stale choice is never reused.
 */
export function DecisionPanel({
  kind,
  proposalId,
  approvers,
  options = [],
  busy,
  onDecide,
  simulated,
}: {
  kind: Decision["kind"];
  proposalId: string;
  approvers: string[];
  options?: string[];
  busy: boolean;
  onDecide: (d: DecisionInput) => void;
  simulated?: boolean;
}) {
  const [decidedBy, setDecidedBy] = useState("");
  const [reason, setReason] = useState("");
  const [clicked, setClicked] = useState<string | null>(null);

  const name = decidedBy.trim().toLowerCase();
  // an empty list means it could not be loaded: then the backend check alone decides
  const onList = approvers.length === 0 || approvers.some((a) => a.toLowerCase() === name);
  const canDecide = name !== "" && onList && proposalId !== "";
  const hasReason = reason.trim() !== "";
  const choices = choicesFor(kind, options);

  return (
    <div className="rounded-2xl border border-wait/40 bg-wait-soft/50 p-5" data-testid="decision-panel">
      <div className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-wait">
        <ShieldCheck className="size-5" />
        {t.proposal.decide}
        {simulated && <span className="font-normal normal-case text-muted">{t.replay.simulated}</span>}
      </div>
      <div className="grid gap-4 md:grid-cols-[minmax(0,16rem)_1fr]">
        <div>
          <Label htmlFor="approver">{t.decision.approver}</Label>
          {approvers.length > 0 ? (
            <Select id="approver" value={decidedBy} onChange={(e) => setDecidedBy(e.target.value)}>
              <option value="">{t.decision.approverPlaceholder}</option>
              {approvers.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          ) : (
            <Input id="approver" value={decidedBy} onChange={(e) => setDecidedBy(e.target.value)} placeholder={t.decision.approverPlaceholder} />
          )}
        </div>
        <div>
          <Label htmlFor="reason">{t.decision.reason}</Label>
          <Textarea
            id="reason"
            className="min-h-10"
            rows={1}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t.decision.reasonPlaceholder}
          />
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {choices.map((c) => {
          const disabled = busy || !canDecide || (c.needsReason === true && !hasReason);
          return (
            <Button
              key={c.decision}
              variant={c.variant}
              size="lg"
              disabled={disabled}
              data-testid={`decide-${c.decision}`}
              onClick={() => {
                setClicked(c.decision);
                onDecide({ decision: c.decision, decided_by: decidedBy.trim(), reason });
              }}
            >
              {busy && clicked === c.decision ? <Spinner /> : c.icon}
              {busy && clicked === c.decision ? t.thinking.sending : c.label}
            </Button>
          );
        })}
      </div>
      <div className="mt-3 space-y-1 text-sm text-muted">
        {name === "" && (
          <p className="flex items-center gap-1.5" data-testid="locked-hint">
            <Lock className="size-4" />
            {t.decision.lockedHint}
          </p>
        )}
        {name !== "" && !onList && (
          <p className="text-bad" data-testid="approver-hint">
            {t.decision.approverNotListed(decidedBy.trim())}
          </p>
        )}
        {kind === "proposal" && !hasReason && <p data-testid="revise-hint">{t.decision.reviseHint}</p>}
      </div>
    </div>
  );
}
