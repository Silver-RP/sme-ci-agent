"use client";

import { useState } from "react";
import {
  Activity,
  BookOpen,
  CalendarClock,
  ChevronDown,
  CircleCheck,
  CircleX,
  FileSearch,
  GitCompareArrows,
  ListTree,
  ScanSearch,
  Siren,
  Wrench,
} from "lucide-react";
import type { AgentEvent } from "@/lib/events";
import { sortByTime } from "@/lib/events";
import { describeEvent, toolArgChips, toolLabel } from "@/lib/describe";
import { causeLabel, clock, dateTime, groupLabel, kpiLabel, num, pct, shiftLabel, str, type Obj } from "@/lib/format";
import type { HypothesisView, ToolCall } from "@/lib/runModel";
import { stepOfEvent } from "@/lib/runModel";
import { t } from "@/lib/strings";
import { cn } from "@/lib/cn";
import { Badge, Card, CardTitle, ConfidenceBar, EmptyState } from "@/components/ui/primitives";

/** The anomaly Detect found: KPI jump in big numbers (S2/S3 context). */
export function AnomalyCard({ anomaly }: { anomaly: Obj | null }) {
  if (!anomaly) {
    return (
      <Card className="p-5" data-testid="anomaly-card" data-empty="true">
        <CardTitle icon={<Siren />}>{t.anomaly.title}</CardTitle>
        <p className="mt-3 text-muted">{t.anomaly.none}</p>
      </Card>
    );
  }
  return (
    <Card className="animate-fade-up overflow-hidden" data-testid="anomaly-card">
      <div className="border-l-4 border-bad p-5">
        <CardTitle icon={<Siren className="text-bad" />} right={anomaly.planned === true ? <Badge tone="neutral">{t.anomaly.planned}</Badge> : null}>
          {t.anomaly.title}
        </CardTitle>
        <div className="mt-3 flex flex-wrap items-baseline gap-x-3">
          <span className="text-lg font-semibold" data-testid="anomaly-kpi">
            {kpiLabel(anomaly.kpi)}
          </span>
          <span className="text-muted" data-testid="anomaly-where">
            {t.anomaly.machine} {str(anomaly.machine)} · {shiftLabel(anomaly.shift)}
          </span>
        </div>
        <div className="mt-2 flex items-end gap-3">
          <span className="text-5xl font-bold tabular-nums tracking-tight text-bad" data-testid="anomaly-value">
            {pct(anomaly.value)}
          </span>
          <span className="pb-1.5 text-muted">
            {t.anomaly.baseline} {pct(anomaly.baseline)}
          </span>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">{t.anomaly.since}</dt>
          <dd className="font-medium tabular-nums">{dateTime(anomaly.start)}</dd>
          <dt className="text-muted">{t.anomaly.limit}</dt>
          <dd className="font-medium tabular-nums">{pct(anomaly.upper_limit)}</dd>
          {num(anomaly.n_points) !== null && (
            <>
              <dt className="text-muted">{t.anomaly.points}</dt>
              <dd className="font-medium tabular-nums">{num(anomaly.n_points)}</dd>
            </>
          )}
        </dl>
      </div>
    </Card>
  );
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  detect: <ScanSearch />,
  query_logs: <FileSearch />,
  correlate: <GitCompareArrows />,
  get_shift_schedule: <CalendarClock />,
  read_sop: <BookOpen />,
};

/** Each tool call as a card with a readable name and its main arguments (FR-02.1). Newest first. */
export function ActivityFeed({ tools }: { tools: ToolCall[] }) {
  return (
    <Card className="p-5" data-testid="activity-feed">
      <CardTitle icon={<Activity />} right={tools.length > 0 ? <Badge tone="neutral">{tools.length}</Badge> : null}>
        {t.activity.title}
      </CardTitle>
      {tools.length === 0 ? (
        <p className="mt-3 text-muted">{t.activity.empty}</p>
      ) : (
        <ol className="mt-3 space-y-2">
          {[...tools].reverse().map((c) => {
            const chips = toolArgChips(c.args);
            return (
              <li key={c.id} className="animate-fade-up flex gap-3 rounded-xl border border-border p-3" data-testid="tool-card" data-tool={c.tool}>
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent [&>svg]:size-5">
                  {TOOL_ICONS[c.tool] ?? <Wrench />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold" data-testid="tool-name">
                      {toolLabel(c.tool)}
                    </span>
                    {c.ok === false ? (
                      <CircleX className="size-4 text-bad" aria-label={t.activity.failed} />
                    ) : (
                      <CircleCheck className="size-4 text-ok" aria-label={t.activity.ok} />
                    )}
                    <span className="ml-auto text-xs tabular-nums text-muted">{clock(c.ts)}</span>
                  </div>
                  {c.found !== null && <p className="text-sm text-muted">{t.activity.found(c.found)}</p>}
                  {chips.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {chips.map((x) => (
                        <span key={x} className="rounded-md bg-surface-2 px-1.5 py-0.5 text-xs text-muted">
                          {x}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}

/** Hypotheses by Ishikawa group, sorted by confidence; the leading one stands out (FR-02.2). */
export function HypothesisBoard({ hypotheses, insufficient }: { hypotheses: HypothesisView[]; insufficient: boolean }) {
  return (
    <Card className="p-5" data-testid="hypothesis-board">
      <CardTitle icon={<ListTree />} right={insufficient ? <Badge tone="wait">{t.hypotheses.insufficient}</Badge> : null}>
        {t.hypotheses.title}
      </CardTitle>
      {hypotheses.length === 0 ? (
        <p className="mt-3 text-muted">{t.hypotheses.empty}</p>
      ) : (
        <ol className="mt-3 space-y-3">
          {hypotheses.map((h, i) => (
            <li
              key={`${h.group}-${h.description}-${i}`}
              className={cn("rounded-xl p-3", i === 0 ? "border border-accent/40 bg-accent-soft/60" : "border border-transparent")}
              data-testid="hypothesis"
              data-leading={i === 0}
            >
              <div className="mb-1 flex items-center gap-2">
                <Badge tone={i === 0 ? "accent" : "neutral"}>{groupLabel(h.group)}</Badge>
                {i === 0 && <span className="text-xs font-semibold uppercase tracking-wide text-accent">{t.hypotheses.leading}</span>}
              </div>
              <p className={cn("mb-2 leading-snug", i === 0 && "font-semibold")}>{causeLabel(h.description)}</p>
              <ConfidenceBar value={h.confidence} />
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

/** Full event log: one sentence per event, JSON only on demand (FR-02.4). */
export function EventLog({ events }: { events: readonly AgentEvent[] }) {
  const [open, setOpen] = useState(false);
  const [json, setJson] = useState<string | null>(null);
  const sorted = sortByTime(events);
  return (
    <Card className="p-5" data-testid="event-log">
      <button className="flex w-full items-center gap-2 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <CardTitle icon={<ListTree />} right={<Badge tone="neutral">{events.length}</Badge>}>
          {t.log.title}
        </CardTitle>
        <ChevronDown className={cn("ml-2 size-5 text-muted transition", open && "rotate-180")} />
      </button>
      {open &&
        (sorted.length === 0 ? (
          <EmptyState>{t.log.empty}</EmptyState>
        ) : (
          <ol className="mt-4 divide-y divide-border">
            {sorted.map((e) => {
              const step = stepOfEvent(e);
              return (
                <li key={e.event_id} className="py-2.5" data-testid="timeline-item">
                  <div className="grid grid-cols-[5.5rem_9rem_1fr_auto] items-start gap-3">
                    <time dateTime={e.ts} className="text-sm tabular-nums text-muted">
                      {clock(e.ts)}
                    </time>
                    <span className="flex flex-col">
                      <span className="text-sm font-semibold">{t.events[e.type] ?? e.type}</span>
                      <span className="text-xs text-muted" data-testid="agent-label" data-agent={e.agent}>
                        {t.agents[e.agent] ?? e.agent}
                        {step ? ` · ${t.steps[step]}` : ""}
                      </span>
                    </span>
                    <span className="min-w-0 break-words">{describeEvent(e)}</span>
                    <button className="text-xs font-semibold text-accent hover:underline" onClick={() => setJson(json === e.event_id ? null : e.event_id)}>
                      {json === e.event_id ? t.log.hide : t.log.details}
                    </button>
                  </div>
                  {json === e.event_id && (
                    <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-surface-2 p-3 text-xs">{JSON.stringify(e, (k, v) => (k === "sim" ? undefined : v), 2)}</pre>
                  )}
                </li>
              );
            })}
          </ol>
        ))}
    </Card>
  );
}
