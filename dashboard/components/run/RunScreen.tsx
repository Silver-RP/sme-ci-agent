"use client";

import type { ReactNode } from "react";
import { AlertTriangle, Radio, Wifi, WifiOff } from "lucide-react";
import type { RunStatus } from "@/lib/api";
import type { AgentEvent } from "@/lib/events";
import { shortError, str } from "@/lib/format";
import { buildRunModel, phaseOf, stepStates, type Phase } from "@/lib/runModel";
import type { ConnectionStatus } from "@/lib/sources";
import { t } from "@/lib/strings";
import { cn } from "@/lib/cn";
import { Badge, type Tone } from "@/components/ui/primitives";
import { LoopStepper } from "@/components/run/LoopStepper";
import { ProposalStage } from "@/components/run/ProposalStage";
import { ActivityFeed, AnomalyCard, EventLog, HypothesisBoard } from "@/components/run/SidePanels";
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
}) {
  const model = buildRunModel(events);
  const phase = phaseOf(status, model, { started, busy });
  const states = stepStates(phase, model);
  const pending = status?.pending ?? null;
  const simulated = mode === "replay";
  const decide = (kind: "proposal" | "rollback" | "halt") => (d: Parameters<RunActions["decide"]>[2]) =>
    actions.decide(str(pending?.proposal_id), kind, d);
  const errorMsg = status?.state === "error" ? str(status.error) : str(model.finished?.error);
  const retryable = status?.state === "error" ? status.retryable !== false : model.finished?.retryable !== false;

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
          onDecide={decide(phase)}
          simulated={simulated}
        />
      );
      break;
    case "halt":
      stage = <HaltStage pending={pending ?? {}} approvers={approvers} busy={busy} onDecide={decide("halt")} simulated={simulated} />;
      break;
    case "error":
      stage = <ErrorStage message={errorMsg} retryable={retryable} busy={busy} onRetry={actions.retry} />;
      break;
    default:
      stage = <OutcomeStage phase={phase} model={model} onNewRun={actions.reset} />;
  }

  return (
    <main className="mx-auto w-full max-w-[1800px] px-4 py-5 md:px-8" data-testid="run-screen">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-[1.75rem] font-semibold tracking-tight">{t.nav.run}</h1>
        {runId && <code className="rounded-md bg-surface-2 px-2 py-0.5 text-sm text-muted">{runId}</code>}
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

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(22rem,1fr)]">
        <section aria-label="Sân khấu" className="min-w-0" data-testid="stage">
          {stage}
        </section>
        <aside className="space-y-5" aria-label={t.activity.title}>
          <AnomalyCard anomaly={model.anomaly} />
          <HypothesisBoard hypotheses={model.hypotheses} insufficient={model.insufficient} />
          <ActivityFeed tools={model.tools} />
        </aside>
      </div>

      <div className="mt-5">
        <EventLog events={events} />
      </div>
    </main>
  );
}
