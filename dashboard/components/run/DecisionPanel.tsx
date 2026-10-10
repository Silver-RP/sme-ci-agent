"use client";

import { useState } from "react";
import { Check, Lock, MessageSquareWarning, RotateCcw, Search, ShieldCheck, Square, X } from "lucide-react";
import type { Decision } from "@/lib/api";
import { t } from "@/lib/strings";
import { Button, Input, Label, Spinner, Textarea } from "@/components/ui/primitives";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
      { decision: "investigate", label: t.decision.investigate, variant: "solid", icon: <Search className="size-4" /> },
      { decision: "finish", label: t.decision.finish, variant: "outline", icon: <Square className="size-4" /> },
    ];
    // the backend says which choices this halt allows (e.g. only "finish" after the total rollback limit)
    return options.length > 0 ? all.filter((c) => options.includes(c.decision)) : all;
  }
  if (kind === "rollback") {
    return [
      { decision: "approved", label: t.decision.approveRollback, variant: "danger", icon: <RotateCcw className="size-4" /> },
      { decision: "rejected", label: t.decision.rejectRollback, variant: "outline", icon: <ShieldCheck className="size-4" /> },
    ];
  }
  return [
    { decision: "approved", label: t.decision.approve, variant: "ok", icon: <Check className="size-4" /> },
    { decision: "rejected", label: t.decision.reject, variant: "outline", icon: <X className="size-4" /> },
    { decision: "revise", label: t.decision.revise, variant: "outline", icon: <MessageSquareWarning className="size-4" />, needsReason: true },
  ];
}

const APPROVER_KEY = "sme.approver";

// sessionStorage: the name is offered again for the next decision in this tab only (3–4 decisions per demo)
function rememberedApprover(): string {
  try {
    return window.sessionStorage.getItem(APPROVER_KEY) ?? "";
  } catch {
    return "";
  }
}
function rememberApprover(name: string) {
  try {
    window.sessionStorage.setItem(APPROVER_KEY, name);
  } catch {
    /* private mode: the name is just not offered again */
  }
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
  defaultApprover,
  busy,
  onDecide,
  simulated,
}: {
  kind: Decision["kind"];
  proposalId: string;
  approvers: string[];
  options?: string[];
  /** replay: the approver of the recording; otherwise the last name chosen in this tab is offered again */
  defaultApprover?: string;
  busy: boolean;
  onDecide: (d: DecisionInput) => void;
  simulated?: boolean;
}) {
  // null until the person touches the field: until then the name is derived, so it also works when the approver
  // list arrives after this panel mounted. Only pre-selects: nothing is sent until a decision button is clicked.
  const [touched, setTouched] = useState<string | null>(null);
  const preferred = defaultApprover || rememberedApprover();
  const decidedBy = touched ?? (approvers.includes(preferred) ? preferred : "");
  const [reason, setReason] = useState("");
  const [clicked, setClicked] = useState<string | null>(null);
  const chooseApprover = (name: string) => {
    setTouched(name);
    rememberApprover(name);
  };

  const name = decidedBy.trim().toLowerCase();
  // an empty list means it could not be loaded: then the backend check alone decides
  const onList = approvers.length === 0 || approvers.some((a) => a.toLowerCase() === name);
  const canDecide = name !== "" && onList && proposalId !== "";
  const hasReason = reason.trim() !== "";
  const choices = choicesFor(kind, options);

  return (
    // Sticks to the bottom of the screen while the approval is on screen, so the reviewer can always reach
    // the buttons without scrolling (one-screen decision, FR-01; the projector font makes the page taller).
    <div
      // same scale as the cards around it: the green Approve button carries the emphasis, not the size; the ring
      // keeps a gap to the content scrolling underneath while the panel is stuck
      className="sticky bottom-3 z-20 rounded-xl border border-wait/50 bg-wait-soft p-4 shadow-card ring-4 ring-bg"
      data-testid="decision-panel"
    >
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-wait">
        <ShieldCheck className="size-4" />
        {t.proposal.decide}
        {simulated && <span className="font-normal normal-case text-muted">{t.replay.simulated}</span>}
      </div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,14rem)_1fr]">
        <div>
          <Label htmlFor="approver" className="sr-only">
            {t.decision.approver}
          </Label>
          {approvers.length > 0 ? (
            // "" shows the placeholder (Radix resets to it on an empty value)
            <Select value={decidedBy} onValueChange={chooseApprover}>
              <SelectTrigger id="approver" className="bg-surface">
                <SelectValue placeholder={t.decision.approverPlaceholder} />
              </SelectTrigger>
              <SelectContent>
                {approvers.map((a) => (
                  <SelectItem key={a} value={a}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input id="approver" value={decidedBy} onChange={(e) => setTouched(e.target.value)} placeholder={t.decision.approverPlaceholder} />
          )}
        </div>
        <div>
          <Label htmlFor="reason" className="sr-only">
            {t.decision.reason}
          </Label>
          <Textarea
            id="reason"
            className="min-h-9 py-1.5"
            rows={1}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={kind === "halt" ? t.decision.reasonPlaceholderHalt : `${t.decision.reason}: ${t.decision.reasonPlaceholder.toLowerCase()}`}
          />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        {choices.map((c) => {
          const disabled = busy || !canDecide || (c.needsReason === true && !hasReason);
          return (
            <Button
              key={c.decision}
              variant={c.variant}
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
        {/* one short hint at a time: what is still missing before a button unlocks; it takes its own line
            rather than being squeezed next to the buttons into one word per line */}
        <div className="min-w-[16rem] flex-1 text-sm text-muted xl:text-right">
          {name === "" ? (
            <p className="inline-flex items-center gap-1.5" data-testid="locked-hint">
              <Lock className="size-4" />
              {t.decision.lockedHint}
            </p>
          ) : !onList ? (
            <p className="text-bad" data-testid="approver-hint">
              {t.decision.approverNotListed(decidedBy.trim())}
            </p>
          ) : kind === "proposal" && !hasReason ? (
            <p data-testid="revise-hint">{t.decision.reviseHint}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
