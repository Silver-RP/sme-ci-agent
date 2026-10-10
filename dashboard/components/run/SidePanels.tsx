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
          <span className="font-semibold" data-testid="anomaly-kpi">
            {kpiLabel(anomaly.kpi)}
          </span>
          <span className="text-muted" data-testid="anomaly-where">
            {t.anomaly.machine} {str(anomaly.machine)} · {shiftLabel(anomaly.shift)}
          </span>
        </div>
        <div className="mt-2 flex items-end gap-3">
          <span className="text-4xl font-bold tabular-nums tracking-tight text-bad" data-testid="anomaly-value">
            {pct(anomaly.value)}
          </span>
          <span className="pb-1.5 text-muted">
            {t.anomaly.baseline} {pct(anomaly.baseline)}
          </span>
        </div>
        {/* one wrapping row per fact: in a narrow card the value drops under its label instead of overflowing */}
        <dl className="mt-4 space-y-1 text-sm">
          {[
            [t.anomaly.since, dateTime(anomaly.start)],
            [t.anomaly.limit, pct(anomaly.upper_limit)],
            ...(num(anomaly.n_points) !== null ? [[t.anomaly.points, String(num(anomaly.n_points))]] : []),
          ].map(([label, value]) => (
            <div key={label} className="flex flex-wrap justify-between gap-x-4">
              <dt className="text-muted">{label}</dt>
              <dd className="font-medium tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </Card>
  );
}

/**
 * One-line context for narrow screens and the projector on a laptop: the anomaly and the leading hypothesis,
 * with a button to open the full side panels. Replaces the right column below 2xl, where it took a third of the width.
 */
export function ContextStrip({
  anomaly,
  hypotheses,
  tools,
  open,
  onToggle,
}: {
  anomaly: Obj | null;
  hypotheses: HypothesisView[];
  tools: ToolCall[];
  open: boolean;
  onToggle: () => void;
}) {
  const lead = hypotheses[0];
  return (
    <Card className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 lg:flex-nowrap" data-testid="context-strip">
      {anomaly ? (
        <span className="flex shrink-0 items-baseline gap-2">
          <Siren className="size-4 self-center text-bad" />
          <span className="font-semibold">{kpiLabel(anomaly.kpi)}</span>
          <span className="text-2xl font-bold tabular-nums text-bad">{pct(anomaly.value)}</span>
          <span className="text-sm text-muted">
            {t.anomaly.baseline} {pct(anomaly.baseline)}
            {/* machine and shift drop first when the strip runs out of room */}
            <span className="hidden xl:inline">
              {" "}
              · {t.anomaly.machine} {str(anomaly.machine)} · {shiftLabel(anomaly.shift)}
            </span>
          </span>
        </span>
      ) : (
        <span className="text-muted">{t.anomaly.none}</span>
      )}
      {lead && (
        <span className="flex min-w-0 items-center gap-2">
          <ListTree className="size-4 shrink-0 text-muted" />
          <Badge tone="accent">{groupLabel(lead.group)}</Badge>
          <span className="truncate font-medium">{causeLabel(lead.description)}</span>
          {lead.confidence !== null && <span className="text-sm tabular-nums text-muted">{Math.round(lead.confidence * 100)}%</span>}
        </span>
      )}
      <button
        className="ml-auto flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold whitespace-nowrap text-accent transition hover:bg-accent-soft active:bg-accent-soft"
        onClick={onToggle}
        aria-expanded={open}
        data-testid="context-toggle"
      >
        {open ? t.context.hide : t.context.show(tools.length)}
        <ChevronDown className={cn("size-4 transition", open && "rotate-180")} />
      </button>
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

/** "+N earlier / more" under a shortened list, so a long run never pushes the stage below the fold. */
function MoreLine({ hidden, label }: { hidden: number; label: (n: number) => string }) {
  if (hidden <= 0) return null;
  return (
    <p className="mt-2 text-sm text-muted" data-testid="more-line">
      {label(hidden)}
    </p>
  );
}

/**
 * Each tool call as a card with a readable name and its main arguments (FR-02.1). Newest first.
 * `limit`: only the newest calls, one line each without argument chips (the side-by-side view under the context
 * strip is about 220px wide per card); the event log keeps the full detail.
 */
export function ActivityFeed({ tools, limit }: { tools: ToolCall[]; limit?: number }) {
  const shown = [...tools].reverse().slice(0, limit ?? tools.length);
  const compact = limit !== undefined;
  return (
    <Card className="p-5" data-testid="activity-feed">
      <CardTitle icon={<Activity />} right={tools.length > 0 ? <Badge tone="neutral">{tools.length}</Badge> : null}>
        {t.activity.title}
      </CardTitle>
      {tools.length === 0 ? (
        <p className="mt-3 text-muted">{t.activity.empty}</p>
      ) : (
        <ol className="mt-3 space-y-2">
          {shown.map((c) => {
            const chips = toolArgChips(c.args);
            if (compact) {
              return (
                <li key={c.id} className="flex items-center gap-2" data-testid="tool-card" data-tool={c.tool}>
                  {c.ok === false ? (
                    <CircleX className="size-4 shrink-0 text-bad" aria-label={t.activity.failed} />
                  ) : (
                    <CircleCheck className="size-4 shrink-0 text-ok" aria-label={t.activity.ok} />
                  )}
                  <span className="min-w-0 truncate font-medium" data-testid="tool-name" title={chips.join(" · ")}>
                    {toolLabel(c.tool)}
                  </span>
                  <span className="ml-auto shrink-0 text-xs tabular-nums text-muted">{clock(c.ts)}</span>
                </li>
              );
            }
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
                        <span key={x} className="max-w-full rounded-md bg-surface-2 px-1.5 py-0.5 text-xs break-all text-muted">
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
      <MoreLine hidden={tools.length - shown.length} label={t.activity.earlier} />
    </Card>
  );
}

/**
 * Hypotheses by Ishikawa group, sorted by confidence; the leading one stands out (FR-02.2).
 * `limit`: only the strongest ones (side-by-side view under the context strip).
 */
export function HypothesisBoard({ hypotheses, insufficient, limit }: { hypotheses: HypothesisView[]; insufficient: boolean; limit?: number }) {
  const shown = hypotheses.slice(0, limit ?? hypotheses.length);
  return (
    <Card className="p-5" data-testid="hypothesis-board">
      <CardTitle icon={<ListTree />} right={insufficient ? <Badge tone="wait">{t.hypotheses.insufficient}</Badge> : null}>
        {t.hypotheses.title}
      </CardTitle>
      {hypotheses.length === 0 ? (
        <p className="mt-3 text-muted">{t.hypotheses.empty}</p>
      ) : (
        <ol className="mt-3 space-y-3">
          {shown.map((h, i) => (
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
              <p className={cn("mb-2 leading-snug wrap-break-word", i === 0 && "font-semibold")}>{causeLabel(h.description)}</p>
              <ConfidenceBar value={h.confidence} />
            </li>
          ))}
        </ol>
      )}
      <MoreLine hidden={hypotheses.length - shown.length} label={t.hypotheses.more} />
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
