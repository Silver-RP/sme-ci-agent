"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BookOpenCheck,
  ChartLine,
  CheckCircle2,
  ChevronDown,
  CircleCheck,
  CirclePause,
  CircleSlash,
  CircleX,
  Hourglass,
  MessageCircleQuestion,
  Play,
  RefreshCw,
  RotateCcw,
  ScrollText,
  Send,
  ShieldCheck,
  Sparkles,
  UserCheck,
  XCircle,
} from "lucide-react";
import { friendlyError, toolArgChips, toolLabel } from "@/lib/describe";
import { isObj, shortError, str, type Obj } from "@/lib/format";
import { t } from "@/lib/strings";
import { cn } from "@/lib/cn";
import type { RunModel } from "@/lib/runModel";
import { Button, buttonClasses, Card, Input, Label, Spinner, Textarea } from "@/components/ui/primitives";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DecisionPanel } from "@/components/run/DecisionPanel";
import { KaizenCard } from "@/components/run/KaizenCard";
import { MeasurementCard } from "@/components/run/MeasurementCard";
import { TechDetail } from "@/components/run/TechDetail";
import type { DecisionInput } from "@/components/run/types";

type Tone = "ok" | "bad" | "wait" | "run";
const TONE_TEXT: Record<Tone, string> = { ok: "text-ok", bad: "text-bad", wait: "text-wait", run: "text-run" };

/** Title of a stage. The status pill next to the page title already names the state, so no badge here. */
function StageHeader({ tone, icon, title, lead }: { tone: Tone; icon: React.ReactNode; title: string; lead?: string }) {
  return (
    <div className="mb-5">
      <h2 className="flex items-center gap-2 text-2xl font-semibold leading-tight tracking-tight" data-testid="stage-title">
        <span className={cn("shrink-0 [&>svg]:size-6", TONE_TEXT[tone])}>{icon}</span>
        {title}
      </h2>
      {lead && <p className="mt-2 max-w-3xl text-muted">{lead}</p>}
    </div>
  );
}

/** Before a run: one big action and what the audience is about to see (FR-04, S2 entry). */
export function StartStage({ onStart, busy }: { onStart: (changeTime: string) => void; busy: boolean }) {
  const [changeTime, setChangeTime] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const promises = [
    { icon: <ShieldCheck />, text: t.start.expect.readOnly },
    { icon: <UserCheck />, text: t.start.expect.approval },
    { icon: <RotateCcw />, text: t.start.expect.rollback },
  ];
  return (
    <Card className="animate-fade-up overflow-hidden" data-testid="start-stage">
      <div className="relative grid gap-8 p-6 md:p-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-accent/10 blur-3xl" />
        <div className="relative">
          <Sparkles className="mb-3 size-8 text-accent" />
          <h2 className="text-2xl font-semibold leading-tight tracking-tight">{t.start.title}</h2>
          <p className="mt-2 max-w-2xl text-muted">{t.start.lead}</p>
          <ul className="mt-4 flex flex-wrap gap-2">
            {t.start.facts.map((f) => (
              <li key={f} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-sm font-semibold text-muted">
                {f}
              </li>
            ))}
          </ul>
          <form
            className="mt-6"
            onSubmit={(e) => {
              e.preventDefault();
              onStart(changeTime.trim());
            }}
          >
            <Button type="submit" size="lg" disabled={busy} data-testid="start-button">
              {busy ? <Spinner /> : <Play className="size-5" />}
              {t.start.button}
            </Button>
            <div className="mt-5">
              <button
                type="button"
                className="flex items-center gap-1 rounded text-sm font-semibold text-muted transition hover:text-fg active:text-fg"
                onClick={() => setAdvanced(!advanced)}
                aria-expanded={advanced}
              >
                <ChevronDown className={cn("size-4 transition", advanced && "rotate-180")} />
                {t.start.advanced}
              </button>
              {advanced && (
                <div className="mt-3 max-w-md">
                  <Label htmlFor="change-time">{t.start.changeTime}</Label>
                  <Input id="change-time" value={changeTime} onChange={(e) => setChangeTime(e.target.value)} placeholder="2026-06-23T22:00:00" />
                </div>
              )}
            </div>
          </form>
          <Link href="/?source=fixture&file=run-happy" className="mt-5 inline-block rounded text-sm font-semibold text-accent hover:underline active:opacity-70">
            {t.start.replayLink} →
          </Link>
        </div>
        <div className="relative self-start rounded-xl border border-border bg-surface-2/60 p-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">{t.start.expectTitle}</h3>
          <ul className="space-y-3">
            {promises.map((p) => (
              <li key={p.text} className="flex gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent [&>svg]:size-4">{p.icon}</span>
                <span className="pt-1 leading-snug">{p.text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}

/**
 * While the LLM works (15–20 s with the real one, FR-02.3, NFR-4): the steps the agent actually took so far, then
 * the step in progress. This is the moment the audience watches the agent investigate, so no placeholder boxes.
 */
export function ThinkingStage({ model, applying }: { model: RunModel; applying?: boolean }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  const messages = t.thinking.messages;
  const msg = applying ? t.thinking.applying : messages[Math.floor(elapsed / 3) % messages.length];
  const done = model.tools.slice(-5);
  return (
    <Card className="animate-fade-up p-6" data-testid="thinking-stage" aria-live="polite">
      <div className="flex items-center gap-4">
        <div className="relative grid size-12 shrink-0 place-items-center rounded-full bg-accent-soft">
          <span className="absolute inset-0 animate-pulse-ring rounded-full" />
          <Sparkles className="size-6 text-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-accent">{t.thinking.title}</div>
          <p className="text-xl font-semibold" data-testid="thinking-message">
            {msg}
          </p>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted">
            <span className="flex gap-1" aria-hidden>
              {[0, 1, 2].map((d) => (
                <span key={d} className="size-1.5 animate-dot rounded-full bg-accent" style={{ animationDelay: `${d * 0.2}s` }} />
              ))}
            </span>
            {elapsed > 0 ? `${t.thinking.elapsed(elapsed)} · ` : ""}
            {t.thinking.note}
          </p>
        </div>
      </div>
      {done.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t.thinking.stepsTitle}</h3>
          <ol className="space-y-2" data-testid="thinking-steps">
            {done.map((c) => {
              const chips = toolArgChips(c.args);
              return (
                <li key={c.id} className="animate-fade-up flex items-start gap-2.5">
                  {c.ok === false ? <CircleX className="mt-0.5 size-5 shrink-0 text-bad" /> : <CircleCheck className="mt-0.5 size-5 shrink-0 text-ok" />}
                  <span className="min-w-0">
                    <span className="font-medium">{toolLabel(c.tool)}</span>
                    {c.found !== null && <span className="text-muted"> · {t.activity.found(c.found)}</span>}
                    {chips.length > 0 && <span className="text-sm text-muted"> · {chips.join(" · ")}</span>}
                  </span>
                </li>
              );
            })}
            <li className="flex items-center gap-2.5 text-accent">
              <Spinner className="mx-0.5" />
              <span className="font-medium">{msg}</span>
            </li>
          </ol>
        </div>
      )}
    </Card>
  );
}

/**
 * Question from the agent (S4, FR-05). The "too few points after the change" question of Measure only needs a
 * confirmation (the backend re-measures and does not read the text, H-34), so it gets one button and an optional
 * note; the backend's English sentence is folded away. FR-05 changed on purpose by vai D (dashboard/README.md).
 */
export function QuestionStage({
  pending,
  model,
  evidence,
  busy,
  onAnswer,
  simulated,
}: {
  pending: Obj;
  model: RunModel;
  evidence: boolean;
  busy: boolean;
  onAnswer: (text: string) => void;
  simulated?: boolean;
}) {
  const [answer, setAnswer] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const q = model.question;
  const question = str(pending.question);

  if (evidence) {
    return (
      <Card className="animate-fade-up p-6" data-testid="question-stage" data-kind="evidence">
        <StageHeader tone="wait" icon={<Hourglass />} title={t.question.evidenceTitle} lead={t.question.evidenceLead} />
        {model.lastMeasurement && (
          <div className="mb-5">
            <MeasurementCard m={model.lastMeasurement} compact />
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onAnswer(answer.trim() || t.question.evidenceAnswer);
          }}
        >
          {noteOpen ? (
            <div className="mb-3">
              <Label htmlFor="answer">{t.question.label}</Label>
              <Textarea id="answer" rows={2} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={t.question.notePlaceholder} />
            </div>
          ) : (
            <button
              type="button"
              className="mb-3 rounded text-sm font-semibold text-accent hover:underline active:opacity-70"
              onClick={() => setNoteOpen(true)}
            >
              + {t.question.addNote}
            </button>
          )}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy} data-testid="answer-submit">
              {busy ? <Spinner /> : <RefreshCw className="size-4" />}
              {busy ? t.thinking.sending : t.question.evidenceConfirm}
            </Button>
            {simulated && <span className="text-sm text-muted">{t.replay.simulated}</span>}
          </div>
        </form>
        {question && <TechDetail className="mt-4">{question}</TechDetail>}
      </Card>
    );
  }

  return (
    <Card className="animate-fade-up p-6" data-testid="question-stage" data-kind="question">
      <StageHeader tone="wait" icon={<MessageCircleQuestion />} title={t.question.title} lead={t.question.lead} />
      <blockquote className="relative rounded-xl border-l-4 border-wait bg-wait-soft/60 p-4 text-lg font-medium leading-relaxed" data-testid="pending-question">
        {question || t.question.fallback}
      </blockquote>
      {q?.attempt !== null && q?.attempt !== undefined && q.max !== null && (
        <p className="mt-2 text-sm font-semibold text-wait" data-testid="question-attempt">
          {t.question.attempt(q.attempt, q.max)}
        </p>
      )}
      <form
        className="mt-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (answer.trim() === "") return;
          onAnswer(answer.trim());
        }}
      >
        <Label htmlFor="answer">{t.question.label}</Label>
        <Textarea id="answer" rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={t.question.placeholder} />
        <div className="mt-3 flex items-center gap-3">
          <Button type="submit" disabled={busy || answer.trim() === ""} data-testid="answer-submit">
            {busy ? <Spinner /> : <Send className="size-4" />}
            {busy ? t.thinking.sending : t.question.send}
          </Button>
          {simulated && <span className="text-sm text-muted">{t.replay.simulated}</span>}
        </div>
      </form>
    </Card>
  );
}

/** Run stopped at a limit (FR-06.2): reason in plain words, choices from `options`. */
export function HaltStage({
  pending,
  approvers,
  defaultApprover,
  busy,
  onDecide,
  simulated,
}: {
  pending: Obj;
  approvers: string[];
  defaultApprover?: string;
  busy: boolean;
  onDecide: (d: DecisionInput) => void;
  simulated?: boolean;
}) {
  const reason = str(pending.reason);
  const options = Array.isArray(pending.options) ? pending.options.map(str) : [];
  const sopVersion = pending.sop_version === null || pending.sop_version === undefined ? "" : ` v${str(pending.sop_version)}`;
  return (
    <div className="animate-fade-up space-y-5" data-testid="proposal-card" data-kind="halt">
      <Card className="p-6">
        <div className="mb-5">
          <h2 className="flex items-center gap-2 text-2xl font-semibold leading-tight tracking-tight" data-testid="approval-title">
            <CirclePause className="size-6 shrink-0 text-wait" />
            {t.halt.title}
          </h2>
          <p className="mt-2 max-w-3xl text-muted" data-testid="halt-explain">
            {t.halt.lead}
          </p>
        </div>
        <div className="flex items-start gap-3 rounded-xl bg-surface-2 p-4">
          <AlertTriangle className="mt-0.5 size-6 shrink-0 text-wait" />
          <p className="text-lg font-semibold" data-testid="halt-reason">
            {t.halt.reasons[reason] ?? reason}
          </p>
        </div>
        {pending.sop_still_in_force === true && (
          <p className="mt-4 flex items-center gap-2 font-medium" data-testid="sop-in-force">
            <ShieldCheck className="size-5 text-ok" />
            {t.halt.sopInForce(`${str(pending.sop_id)}${sopVersion}`)}
          </p>
        )}
        {reason && t.halt.reasons[reason] && <TechDetail className="mt-4">{reason}</TechDetail>}
      </Card>
      <DecisionPanel
        key={str(pending.proposal_id)}
        kind="halt"
        proposalId={str(pending.proposal_id)}
        approvers={approvers}
        defaultApprover={defaultApprover}
        options={options}
        busy={busy}
        onDecide={onDecide}
        simulated={simulated}
      />
    </div>
  );
}

/** A run in error that can no longer be retried can be closed by an approver with a reason (H-48). */
function CloseRunForm({ approvers, busy, onClose }: { approvers: string[]; busy: boolean; onClose: (closedBy: string, reason: string) => void }) {
  const [closedBy, setClosedBy] = useState("");
  const [reason, setReason] = useState("");
  const ready = closedBy.trim() !== "" && reason.trim() !== "" && !busy;
  return (
    <form
      className="mt-5 rounded-xl border border-border bg-surface-2/60 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onClose(closedBy.trim(), reason.trim());
      }}
      data-testid="close-run"
    >
      <h3 className="mb-1 font-semibold">{t.error.closeTitle}</h3>
      <p className="mb-3 text-sm text-muted">{t.error.closeHint}</p>
      <div className="grid gap-3 md:grid-cols-[minmax(0,14rem)_1fr]">
        <div>
          <Label htmlFor="close-by" className="sr-only">
            {t.decision.approver}
          </Label>
          {approvers.length > 0 ? (
            <Select value={closedBy} onValueChange={setClosedBy}>
              <SelectTrigger id="close-by">
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
            <Input id="close-by" value={closedBy} onChange={(e) => setClosedBy(e.target.value)} placeholder={t.decision.approverPlaceholder} />
          )}
        </div>
        <div>
          <Label htmlFor="close-reason" className="sr-only">
            {t.error.closeReason}
          </Label>
          <Input id="close-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t.error.closeReason} />
        </div>
      </div>
      <Button type="submit" variant="danger" className="mt-3" disabled={!ready} data-testid="close-run-submit">
        {busy ? <Spinner /> : <XCircle className="size-4" />}
        {t.error.closeButton}
      </Button>
    </form>
  );
}

/** Error in plain words, Retry only when the backend says it can be retried (FR-04.2), otherwise Close. */
export function ErrorStage({
  message,
  retryable,
  busy,
  onRetry,
  onClose,
  approvers = [],
}: {
  message: string;
  retryable: boolean;
  busy: boolean;
  onRetry: () => void;
  onClose?: (closedBy: string, reason: string) => void;
  approvers?: string[];
}) {
  return (
    <Card className="animate-fade-up border-bad/40 p-6" data-testid="run-error">
      <StageHeader tone="bad" icon={<AlertTriangle />} title={t.error.title} />
      <p role="alert" className="text-lg font-semibold text-bad" data-testid="run-error-message">
        {friendlyError(message)}
      </p>
      {/* FR-04.2 asks for the first line of `error` on screen (never the traceback): kept visible, under the plain words */}
      <p className="mt-1 rounded-lg bg-bad-soft px-3 py-1.5 font-mono text-sm text-bad" data-testid="run-error-raw">
        {shortError(message) || t.common.noData}
      </p>
      {retryable && <p className="mt-1 text-muted">{t.error.safe}</p>}
      <div className="mt-5">
        {retryable ? (
          <Button onClick={onRetry} disabled={busy} data-testid="retry-button">
            {busy ? <Spinner /> : <RefreshCw className="size-4" />}
            {busy ? t.error.retrying : t.error.retry}
          </Button>
        ) : (
          <>
            <p className="text-muted" data-testid="not-retryable">
              {t.error.notRetryable}
            </p>
            {onClose && <CloseRunForm approvers={approvers} busy={busy} onClose={onClose} />}
          </>
        )}
      </div>
    </Card>
  );
}

/** How a run ended: completed (with the kaizen card), closed by a person, or nothing abnormal (H-24). */
export function OutcomeStage({
  phase,
  model,
  runId,
  onNewRun,
}: {
  phase: "completed" | "closed" | "no_anomaly" | "finished";
  model: RunModel;
  runId?: string | null;
  onNewRun?: () => void;
}) {
  const conf =
    phase === "completed"
      ? { tone: "ok" as const, icon: <CheckCircle2 />, title: t.outcome.completedTitle, lead: t.outcome.completedLead }
      : phase === "no_anomaly"
        ? { tone: "ok" as const, icon: <ShieldCheck />, title: t.outcome.noAnomalyTitle, lead: t.outcome.noAnomalyLead }
        : { tone: "run" as const, icon: <CircleSlash />, title: t.outcome.closedTitle, lead: t.outcome.closedLead };
  const passedMeasurement = [...model.measurements].reverse().find((m) => m.status === "measured");
  const content = model.learning && isObj(model.learning.content) ? model.learning.content : null;
  // what to look at next, so the story does not end on a dead screen
  const links = [
    content && { href: "/kaizen", label: t.outcome.links.kaizen, icon: <BookOpenCheck className="size-4" /> },
    runId && { href: `/audit?run=${encodeURIComponent(runId)}`, label: t.outcome.links.audit, icon: <ScrollText className="size-4" /> },
    { href: "/overview", label: t.outcome.links.overview, icon: <ChartLine className="size-4" /> },
  ].filter(Boolean) as { href: string; label: string; icon: React.ReactNode }[];
  return (
    <div className="animate-fade-up space-y-5" data-testid="outcome-stage" data-phase={phase}>
      <Card className={cn("p-6", phase === "completed" && "border-ok/40")}>
        <StageHeader tone={conf.tone} icon={conf.icon} title={conf.title} lead={conf.lead} />
        {phase === "completed" && passedMeasurement && <MeasurementCard m={passedMeasurement} />}
        <div className="mt-6 flex flex-wrap items-center gap-2" data-testid="outcome-links">
          {onNewRun && (
            <Button onClick={onNewRun} data-testid="new-run">
              <Play className="size-4" />
              {t.outcome.newRun}
            </Button>
          )}
          {links.map((l) => (
            <Link key={l.href} href={l.href} className={buttonClasses("outline", "md")}>
              {l.icon}
              {l.label}
            </Link>
          ))}
        </div>
      </Card>
      {content && <KaizenCard content={content} outcome={str(content.outcome)} />}
    </div>
  );
}
