"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CirclePause,
  CircleSlash,
  Hourglass,
  MessageCircleQuestion,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { isObj, shortError, str, type Obj } from "@/lib/format";
import { t } from "@/lib/strings";
import { cn } from "@/lib/cn";
import type { RunModel } from "@/lib/runModel";
import { Badge, Button, Card, Input, Label, Spinner, Textarea } from "@/components/ui/primitives";
import { DecisionPanel } from "@/components/run/DecisionPanel";
import { KaizenCard } from "@/components/run/KaizenCard";
import { MeasurementCard } from "@/components/run/MeasurementCard";
import type { DecisionInput } from "@/components/run/types";

function StageHeader({ tone, badge, icon, title, lead }: { tone: "ok" | "bad" | "wait" | "run"; badge: string; icon: React.ReactNode; title: string; lead?: string }) {
  return (
    <div className="mb-5">
      <Badge tone={tone} className="mb-2">
        {icon}
        {badge}
      </Badge>
      <h2 className="text-[1.75rem] font-semibold leading-tight tracking-tight" data-testid="stage-title">
        {title}
      </h2>
      {lead && <p className="mt-2 max-w-3xl text-muted">{lead}</p>}
    </div>
  );
}

/** Before a run: one big action, with the change time tucked away (FR-04, S2 entry). */
export function StartStage({ onStart, busy }: { onStart: (changeTime: string) => void; busy: boolean }) {
  const [changeTime, setChangeTime] = useState("");
  const [advanced, setAdvanced] = useState(false);
  return (
    <Card className="animate-fade-up overflow-hidden" data-testid="start-stage">
      <div className="relative p-8 md:p-10">
        <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-accent/10 blur-3xl" />
        <Sparkles className="mb-4 size-10 text-accent" />
        <h2 className="text-[2rem] font-semibold leading-tight tracking-tight">{t.start.title}</h2>
        <p className="mt-3 max-w-2xl text-lg text-muted">{t.start.lead}</p>
        <ul className="mt-5 flex flex-wrap gap-2">
          {t.start.facts.map((f) => (
            <li key={f}>
              <Badge tone="neutral">{f}</Badge>
            </li>
          ))}
        </ul>
        <form
          className="mt-8"
          onSubmit={(e) => {
            e.preventDefault();
            onStart(changeTime.trim());
          }}
        >
          <Button type="submit" size="lg" disabled={busy} className="h-14 px-8 text-xl" data-testid="start-button">
            {busy ? <Spinner /> : <Play className="size-6" />}
            {t.start.button}
          </Button>
          <div className="mt-6">
            <button
              type="button"
              className="flex items-center gap-1 text-sm font-semibold text-muted hover:text-fg"
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
        <Link href="/?source=fixture&file=run-happy" className="mt-6 inline-block text-sm font-semibold text-accent hover:underline">
          {t.start.replayLink} →
        </Link>
      </div>
    </Card>
  );
}

/** While the LLM works (15–20 s): never a blank screen (FR-02.3, NFR-4). */
export function ThinkingStage({ model, applying }: { model: RunModel; applying?: boolean }) {
  const [i, setI] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => {
      setI((x) => x + 1);
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);
  const messages = t.thinking.messages;
  const msg = applying ? t.thinking.applying : messages[Math.floor(i / 3) % messages.length];
  const last = model.tools.at(-1);
  return (
    <Card className="animate-fade-up p-8" data-testid="thinking-stage" aria-live="polite">
      <div className="flex items-center gap-5">
        <div className="relative grid size-16 shrink-0 place-items-center rounded-full bg-accent-soft">
          <span className="absolute inset-0 animate-pulse-ring rounded-full" />
          <Sparkles className="size-7 text-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold uppercase tracking-wide text-accent">{t.thinking.title}</div>
          <p className="text-2xl font-semibold" data-testid="thinking-message">
            {msg}
          </p>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted">
            <span className="flex gap-1" aria-hidden>
              {[0, 1, 2].map((d) => (
                <span key={d} className="size-1.5 animate-dot rounded-full bg-accent" style={{ animationDelay: `${d * 0.2}s` }} />
              ))}
            </span>
            {elapsed > 0 ? `${elapsed}s · ` : ""}
            {t.thinking.note}
          </p>
        </div>
      </div>
      {last && (
        <p className="mt-6 border-t border-border pt-4 text-muted">
          {t.tools[last.tool] ?? last.tool} · {last.ok === false ? t.activity.failed : t.activity.ok}
        </p>
      )}
      <div className="mt-6 grid gap-3 md:grid-cols-3">
        {[0, 1, 2].map((k) => (
          <div key={k} className="h-20 animate-shimmer rounded-xl bg-[linear-gradient(90deg,var(--surface-2)_0%,var(--border)_50%,var(--surface-2)_100%)] bg-[length:200%_100%]" />
        ))}
      </div>
    </Card>
  );
}

/** Question from the agent (S4, FR-05); also the "not enough points after the change" question of Measure. */
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
  const q = model.question;
  return (
    <Card className="animate-fade-up p-6 md:p-8" data-testid="question-stage">
      <StageHeader
        tone="wait"
        badge={t.status.waitAnswer}
        icon={evidence ? <Hourglass className="size-4" /> : <MessageCircleQuestion className="size-4" />}
        title={evidence ? t.question.evidenceTitle : t.question.title}
        lead={evidence ? t.question.evidenceLead : t.question.lead}
      />
      {evidence && model.lastMeasurement && (
        <div className="mb-5">
          <MeasurementCard m={model.lastMeasurement} compact />
        </div>
      )}
      <blockquote className="relative rounded-2xl border-l-4 border-wait bg-wait-soft/60 p-5 text-xl font-medium leading-relaxed" data-testid="pending-question">
        {str(pending.question) || t.question.fallback}
      </blockquote>
      {!evidence && q?.attempt !== null && q?.attempt !== undefined && q.max !== null && (
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
          <Button type="submit" size="lg" disabled={busy || answer.trim() === ""} data-testid="answer-submit">
            {busy ? <Spinner /> : <Send className="size-5" />}
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
  busy,
  onDecide,
  simulated,
}: {
  pending: Obj;
  approvers: string[];
  busy: boolean;
  onDecide: (d: DecisionInput) => void;
  simulated?: boolean;
}) {
  const reason = str(pending.reason);
  const options = Array.isArray(pending.options) ? pending.options.map(str) : [];
  const sopVersion = pending.sop_version === null || pending.sop_version === undefined ? "" : ` v${str(pending.sop_version)}`;
  return (
    <div className="animate-fade-up space-y-5" data-testid="proposal-card" data-kind="halt">
      <Card className="p-6 md:p-8">
        <div className="mb-5">
          <Badge tone="wait" className="mb-2">
            <CirclePause className="size-4" />
            {t.status.halted}
          </Badge>
          <h2 className="text-[1.75rem] font-semibold leading-tight tracking-tight" data-testid="approval-title">
            {t.halt.title}
          </h2>
          <p className="mt-2 max-w-3xl text-muted" data-testid="halt-explain">
            {t.halt.lead}
          </p>
        </div>
        <div className="flex items-start gap-3 rounded-xl bg-surface-2 p-4">
          <AlertTriangle className="mt-0.5 size-6 shrink-0 text-wait" />
          <div>
            <p className="text-xl font-semibold" data-testid="halt-reason">
              {t.halt.reasons[reason] ?? reason}
            </p>
            {reason && t.halt.reasons[reason] && <code className="text-sm text-muted">{reason}</code>}
          </div>
        </div>
        {pending.sop_still_in_force === true && (
          <p className="mt-4 flex items-center gap-2 font-medium" data-testid="sop-in-force">
            <ShieldCheck className="size-5 text-ok" />
            {t.halt.sopInForce(`${str(pending.sop_id)}${sopVersion}`)}
          </p>
        )}
      </Card>
      <DecisionPanel
        key={str(pending.proposal_id)}
        kind="halt"
        proposalId={str(pending.proposal_id)}
        approvers={approvers}
        options={options}
        busy={busy}
        onDecide={onDecide}
        simulated={simulated}
      />
    </div>
  );
}

/** Error with Retry only when the backend says it can be retried (FR-04.2). */
export function ErrorStage({
  message,
  retryable,
  busy,
  onRetry,
}: {
  message: string;
  retryable: boolean;
  busy: boolean;
  onRetry: () => void;
}) {
  return (
    <Card className="animate-fade-up border-bad/40 p-6 md:p-8" data-testid="run-error">
      <StageHeader tone="bad" badge={t.status.error} icon={<AlertTriangle className="size-4" />} title={t.error.title} />
      <p role="alert" className="rounded-xl bg-bad-soft p-4 font-mono text-[0.95rem] text-bad" data-testid="run-error-message">
        {shortError(message) || t.common.noData}
      </p>
      <div className="mt-5">
        {retryable ? (
          <Button size="lg" onClick={onRetry} disabled={busy} data-testid="retry-button">
            {busy ? <Spinner /> : <RefreshCw className="size-5" />}
            {busy ? t.error.retrying : t.error.retry}
          </Button>
        ) : (
          <p className="text-muted" data-testid="not-retryable">
            {t.error.notRetryable}
          </p>
        )}
      </div>
    </Card>
  );
}

/** How a run ended: completed (with the kaizen card), closed by a person, or nothing abnormal (H-24). */
export function OutcomeStage({
  phase,
  model,
  onNewRun,
}: {
  phase: "completed" | "closed" | "no_anomaly" | "finished";
  model: RunModel;
  onNewRun?: () => void;
}) {
  const learned = phase === "completed" && model.learning !== null;
  const conf =
    phase === "completed"
      ? { tone: "ok" as const, badge: learned ? t.status.completed : t.status.completedNoLearn, icon: <CheckCircle2 className="size-4" />, title: t.outcome.completedTitle, lead: t.outcome.completedLead }
      : phase === "no_anomaly"
        ? { tone: "ok" as const, badge: t.status.noAnomaly, icon: <ShieldCheck className="size-4" />, title: t.outcome.noAnomalyTitle, lead: t.outcome.noAnomalyLead }
        : { tone: "run" as const, badge: t.status.closed, icon: <CircleSlash className="size-4" />, title: t.outcome.closedTitle, lead: t.outcome.closedLead };
  const passedMeasurement = [...model.measurements].reverse().find((m) => m.status === "measured");
  const content = model.learning && isObj(model.learning.content) ? model.learning.content : null;
  return (
    <div className="animate-fade-up space-y-5" data-testid="outcome-stage" data-phase={phase}>
      <Card className={cn("p-6 md:p-8", phase === "completed" && "border-ok/40")}>
        <StageHeader tone={conf.tone} badge={conf.badge} icon={conf.icon} title={conf.title} lead={conf.lead} />
        {phase === "completed" && passedMeasurement && <MeasurementCard m={passedMeasurement} />}
        {onNewRun && (
          <Button variant="outline" className="mt-6" onClick={onNewRun} data-testid="new-run">
            <Play className="size-4" />
            {t.outcome.newRun}
          </Button>
        )}
      </Card>
      {content && <KaizenCard content={content} outcome={str(content.outcome)} />}
    </div>
  );
}
