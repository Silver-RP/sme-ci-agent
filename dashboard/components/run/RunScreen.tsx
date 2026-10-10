"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, Radio, Wifi, WifiOff } from "lucide-react";
import type { RunStatus } from "@/lib/api";
import type { AgentEvent } from "@/lib/events";
import { num, shortError, str } from "@/lib/format";
import { buildRunModel, phaseOf, stepStates, type Phase } from "@/lib/runModel";
import type { ConnectionStatus } from "@/lib/sources";
import { t } from "@/lib/strings";
import { cn } from "@/lib/cn";
import { Badge, type Tone } from "@/components/ui/primitives";
import { LoopStepper } from "@/components/run/LoopStepper";
import { ProposalStage } from "@/components/run/ProposalStage";
import { ActivityFeed, AnomalyCard, ContextStrip, EventLog, HypothesisBoard } from "@/components/run/SidePanels";
import { ErrorStage, HaltStage, OutcomeStage, QuestionStage, StartStage, ThinkingStage } from "@/components/run/Stages";
import type { RunActions, RunMode } from "@/components/run/types";

const PHASE_STATUS: Record<Phase, { label: string; tone: Tone }> = {
  start: { label: t.status.idle, tone: "neutral" },
  thinking: { label: t.status.running, tone: "run" },
  answer: { label: t.status.waitAnswer, tone: "wait" },
  evidence: { label: t.status.waitAnswer, tone: "wait" },
  proposal: { label: t.status.waitApproval, tone: "wait" },
  rollback: { label: t.status.waitRollback, tone: "wait" },
  halt: { label: t.status.halted, tone: "wait" },
  error: { label: t.status.error, tone: "bad" },
  completed: { label: t.status.completed, tone: "ok" },
  closed: { label: t.status.closed, tone: "run" },
  no_anomaly: { label: t.status.noAnomaly, tone: "ok" },
  finished: { label: t.status.completedNoLearn, tone: "run" },
};

export function RunStatusPill({ phase, learned }: { phase: Phase; learned: boolean }) {
  const s = phase === "completed" && !learned ? { label: t.status.completedNoLearn, tone: "ok" as Tone } : PHASE_STATUS[phase];
  return (
    <Badge tone={s.tone} className="px-3 py-1 text-base" data-testid="run-status" data-phase={phase}>
      <span className={cn("size-2 rounded-full bg-current", (phase === "thinking" || s.tone === "wait") && "animate-pulse")} />
      {s.label}
    </Badge>
  );
}

function ConnectionChip({ status }: { status: ConnectionStatus }) {
  const Icon = status === "disconnected" ? WifiOff : status === "open" ? Radio : Wifi;
  return (
    <Badge tone={status === "disconnected" ? "bad" : "neutral"} data-testid="connection-status" data-status={status}>
      <Icon className="size-4" />
      {t.source.connection[status] ?? status}
    </Badge>
  );
}

/**
 * The run screen (S1–S7): loop on top, one focused "stage" on the left, what the agent did on the right.
 * Shared by live, replay and watch modes; only the controller behind `actions` differs.
 */
export function RunScreen({
  mode,
  runId,
  events,
  invalidEvents = [],
  connection,
  status,
  busy,
  started,
  apiError,
  pastError,
  approvers,
  actions,
  toolbar,
  notice,
  defaultApprover,
}: {
  mode: RunMode;
  runId: string | null;
  events: readonly AgentEvent[];
  invalidEvents?: string[];
  connection: ConnectionStatus;
  status: RunStatus | null;
  busy: boolean;
  started: boolean;
  apiError?: string | null;
  pastError?: string | null;
  approvers: string[];
  actions: RunActions;
  toolbar?: ReactNode;
  /** replay: what the recording does next, shown in the replay banner */
  notice?: string;
  /** replay: the approver the recording uses next, pre-selected in the decision panel */
  defaultApprover?: string;
}) {
  // null = automatic: open while the agent investigates (S3: tool cards and hypotheses must be visible, FR-02),
  // folded once a person has to act so the stage leads; a click by the person overrides it
  const [contextChoice, setContextChoice] = useState<boolean | null>(null);
  const model = buildRunModel(events);
  const phase = phaseOf(status, model, { started, busy });
  const contextOpen = contextChoice ?? phase === "thinking";
  const states = stepStates(phase, model);
  const pending = status?.pending ?? null;
  const simulated = mode === "replay";
  const decide = (kind: "proposal" | "rollback" | "halt") => (d: Parameters<RunActions["decide"]>[2]) =>
    actions.decide(str(pending?.proposal_id), kind, d);
  const errorMsg = status?.state === "error" ? str(status.error) : str(model.finished?.error);
  const retryable = status?.state === "error" ? status.retryable !== false : model.finished?.retryable !== false;
  // Right column from 2xl. Below that the same panels open side by side under the context strip, shortened so a
  // long run (many hypotheses or tool calls) never pushes the stage below the fold; the event log has everything.
  const sidePanels = (short: boolean) => (
    <>
      <AnomalyCard anomaly={model.anomaly} />
      <HypothesisBoard hypotheses={model.hypotheses} insufficient={model.insufficient} limit={short ? 2 : undefined} />
      <ActivityFeed tools={model.tools} limit={short ? 3 : undefined} />
    </>
  );
  // "Dựa trên bằng chứng #n" → the agent's investigation steps (storyboard S5 → S3). evidence_refs index the
  // backend's evidence list, which does not map 1:1 to events, so this opens the steps instead of guessing one.
  const showEvidence = () => {
    setContextChoice(true);
    requestAnimationFrame(() => {
      const feed = [...document.querySelectorAll<HTMLElement>('[data-testid="activity-feed"]')].find((el) => el.offsetParent !== null);
      feed?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  };
  // rollback restores the content the run's first change replaced (sop_applied.previous_version, H-19)
  const restoreVersion = num(model.applied[0]?.previous_version);

  let stage: ReactNode;
  switch (phase) {
    case "start":
      stage = actions.start ? <StartStage onStart={actions.start} busy={busy} /> : <ThinkingStage model={model} />;
      break;
    case "thinking":
      stage = <ThinkingStage model={model} applying={model.reached.includes("improve")} />;
      break;
    case "answer":
    case "evidence":
      stage = (
        <QuestionStage
          key={`${model.question?.attempt ?? 0}-${events.length}`}
          pending={pending ?? {}}
          model={model}
          evidence={phase === "evidence"}
          busy={busy}
          onAnswer={actions.answer}
          simulated={simulated}
        />
      );
      break;
    case "proposal":
    case "rollback":
      stage = (
        <ProposalStage
          pending={pending ?? {}}
          approvers={approvers}
          busy={busy}
          lastMeasurement={model.lastMeasurement}
          restoreVersion={restoreVersion}
          onShowEvidence={showEvidence}
          defaultApprover={defaultApprover}
          onDecide={decide(phase)}
          simulated={simulated}
        />
      );
      break;
    case "halt":
      stage = (
        <HaltStage pending={pending ?? {}} approvers={approvers} defaultApprover={defaultApprover} busy={busy} onDecide={decide("halt")} simulated={simulated} />
      );
      break;
    case "error":
      stage = <ErrorStage message={errorMsg} retryable={retryable} busy={busy} onRetry={actions.retry} onClose={actions.close} approvers={approvers} />;
      break;
    default:
      stage = <OutcomeStage phase={phase} model={model} runId={runId} onNewRun={actions.reset} />;
  }

  return (
    <main className="mx-auto w-full max-w-[1800px] px-4 py-5 md:px-8" data-testid="run-screen">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t.nav.run}</h1>
        {runId && <code className="rounded-md bg-surface-2 px-2 py-0.5 text-sm text-muted present:hidden">{runId}</code>}
        <RunStatusPill phase={phase} learned={model.learning !== null} />
        <div className="ml-auto flex items-center gap-2">
          {toolbar}
          {mode !== "replay" && runId && <ConnectionChip status={connection} />}
        </div>
      </div>

      {simulated && (
        <div className="mb-4 rounded-xl border border-accent/30 bg-accent-soft px-4 py-2 text-sm font-medium text-accent" data-testid="replay-banner">
          {t.source.replayBanner}
          {notice && (
            <span className="ml-2 font-semibold" data-testid="replay-hint">
              · {notice}
            </span>
          )}
        </div>
      )}

      <LoopStepper states={states} showRollback={model.reached.includes("rollback") || phase === "rollback"} />

      {(apiError || pastError || invalidEvents.length > 0) && (
        <div className="mt-4 space-y-2">
          {apiError && (
            <p role="alert" className="flex items-center gap-2 rounded-xl border border-bad/40 bg-bad-soft px-4 py-2 text-bad" data-testid="api-error">
              <AlertTriangle className="size-5 shrink-0" />
              {apiError}
            </p>
          )}
          {pastError && phase !== "error" && (
            <p className="rounded-xl bg-surface-2 px-4 py-2 text-sm text-muted" data-testid="past-error">
              {t.error.past(shortError(pastError))}
            </p>
          )}
          {invalidEvents.length > 0 && (
            <p className="rounded-xl bg-wait-soft px-4 py-2 text-sm text-wait" data-testid="event-errors">
              {t.error.invalidEvents(invalidEvents.length)}
            </p>
          )}
        </div>
      )}

      {/* Two columns only from 2xl (1536px): below that (laptops, the projector at 125%) the right column squeezed
          the stage, so it becomes a one-line strip that opens the full panels on demand. Before a run starts
          the panels would all be empty, so they are not shown. */}
      {phase !== "start" && (
        <div className="mt-5 2xl:hidden">
          <ContextStrip
            anomaly={model.anomaly}
            hypotheses={model.hypotheses}
            tools={model.tools}
            open={contextOpen}
            onToggle={() => setContextChoice(!contextOpen)}
          />
          {/* opens right under the strip that was clicked, not further down where the right column used to be */}
          {contextOpen && (
            // Measured with a long fake run: three columns from md and a height cap per card keep the stage title on
            // a 1366x768 screen. min-w-0 lets a column shrink below an unbreakable string (ids, codes).
            <div
              className="mt-3 grid animate-fade-up items-start gap-4 md:grid-cols-3 *:max-h-72 *:min-w-0 *:overflow-y-auto"
              data-testid="context-panels"
            >
              {sidePanels(true)}
            </div>
          )}
        </div>
      )}
      <div className={cn("mt-5 grid gap-5", phase !== "start" && "2xl:grid-cols-[minmax(0,1.65fr)_minmax(22rem,1fr)]")}>
        <section aria-label="Sân khấu" className="min-w-0" data-testid="stage">
          {model.conflict && (phase === "proposal" || phase === "rollback" || phase === "halt" || phase === "thinking") && (
            <div className="mb-4 flex items-start gap-3 rounded-xl border border-wait/50 bg-wait-soft p-4" role="status" data-testid="sop-conflict">
              <AlertTriangle className="mt-0.5 size-5 shrink-0 text-wait" />
              <div>
                <p className="font-semibold">{model.conflict.kind === "rollback" ? t.conflict.rollbackTitle : t.conflict.approvalTitle}</p>
                <p className="text-sm text-muted">{t.conflict.lead(model.conflict.sopId, model.conflict.currentVersion)}</p>
              </div>
            </div>
          )}
          {stage}
        </section>
        {phase !== "start" && (
          <aside className="hidden space-y-5 2xl:block" aria-label={t.activity.title} data-testid="side-panels">
            {sidePanels(false)}
          </aside>
        )}
      </div>

      {phase !== "start" && (
        <div className="mt-5 present:hidden">
          <EventLog events={events} />
        </div>
      )}
    </main>
  );
}
