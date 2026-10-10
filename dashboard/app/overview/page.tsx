"use client";

import { useState } from "react";
import Link from "next/link";
import { Activity, Gauge, Play, Siren, TrendingUp } from "lucide-react";
import { DataState, RefreshButton } from "@/components/data/DataState";
import { KpiChart } from "@/components/data/KpiChart";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { buttonClasses, Card, CardTitle, Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { dateTime, kpiLabel, pct, shiftLabel } from "@/lib/format";
import { focusAnomaly, getKpiSeries, getMetrics, recentMean, type KpiSeries } from "@/lib/readApi";
import { t } from "@/lib/strings";
import { useApi } from "@/lib/useApi";

// No API lists the machines and shifts yet; these match the sandbox data (GET /kpi/series answers 422 otherwise).
const MACHINES = ["M01", "M02", "M03"];
const SHIFTS = ["morning", "afternoon", "night"];
const ALL = "all";

function Segmented({ value, options, onChange, label }: { value: string; options: { value: string; label: string }[]; onChange: (v: string) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-lg bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-3 py-1 text-sm font-semibold transition active:scale-[0.97]",
            value === o.value ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Stat({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: string; tone?: "bad" | "ok" }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted [&>svg]:size-4">
        {icon}
        {label}
      </div>
      <div className={cn("mt-2 text-3xl font-bold tabular-nums tracking-tight", tone === "bad" && "text-bad", tone === "ok" && "text-ok")}>{value}</div>
    </Card>
  );
}

function SeriesView({ series, onFocus }: { series: KpiSeries; onFocus: (machine: string, shift: string) => void }) {
  const lastWeek = recentMean(series.points, 7);
  const limit = series.upper_limit;
  const currentTone = lastWeek === null || limit === null ? undefined : lastWeek > limit ? "bad" : "ok";
  return (
    <>
      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<Activity />} label={t.overview.stats.current} value={pct(lastWeek)} tone={currentTone} />
        <Stat icon={<Gauge />} label={t.overview.stats.baseline} value={pct(series.baseline)} />
        <Stat icon={<TrendingUp />} label={t.overview.stats.limit} value={pct(limit)} />
        <Stat icon={<Siren />} label={t.overview.stats.anomalies} value={String(series.anomalies.length)} tone={series.anomalies.length ? "bad" : "ok"} />
      </div>
      <Card className="p-5">
        <CardTitle>
          {kpiLabel(series.kpi)} · {series.machine ? `${t.overview.machine} ${series.machine}` : t.overview.allMachines} ·{" "}
          {series.shift ? shiftLabel(series.shift) : t.overview.allShifts}
        </CardTitle>
        {series.machine === null && <p className="mt-1 text-sm text-muted">{t.overview.averaged}</p>}
        <div className="mt-4">
          <KpiChart series={series} />
        </div>
      </Card>
      <Card className="mt-5 overflow-hidden" data-testid="anomaly-list">
        <div className="border-b border-border px-5 py-4">
          <CardTitle icon={<Siren />}>{t.overview.anomalyList}</CardTitle>
        </div>
        {series.anomalies.length === 0 ? (
          <p className="px-5 py-4 text-muted">{t.overview.noAnomaly}</p>
        ) : (
          <ul className="divide-y divide-border">
            {series.anomalies.map((a) => (
              <li key={`${a.machine}-${a.shift}-${a.start}`}>
                <button
                  className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 text-left transition hover:bg-surface-2 active:bg-surface-2"
                  onClick={() => onFocus(a.machine, a.shift)}
                >
                  <span className="font-semibold">
                    {t.overview.machine} {a.machine} · {shiftLabel(a.shift)}
                  </span>
                  <span className="text-sm tabular-nums text-muted">
                    {dateTime(a.start)} → {dateTime(a.end)} · {t.overview.days(Math.round((Date.parse(a.end) - Date.parse(a.start)) / 86_400_000))}
                  </span>
                  <span className="ml-auto text-sm font-semibold text-accent">{t.overview.focus}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

export default function OverviewPage() {
  // null: follow the data (open on the longest anomaly); a person's choice replaces it
  const [filter, setFilter] = useState<{ machine: string; shift: string } | null>(null);
  // the main KPI comes from the domain config; /metrics lists it first
  const metrics = useApi(() => getMetrics(), []);
  const kpi = metrics.data?.[0]?.name ?? null;
  const series = useApi(async () => {
    if (!kpi) return null;
    if (filter) return getKpiSeries({ kpi, machine: filter.machine === ALL ? null : filter.machine, shift: filter.shift === ALL ? null : filter.shift });
    const all = await getKpiSeries({ kpi });
    const focus = focusAnomaly(all.anomalies);
    return focus ? getKpiSeries({ kpi, machine: focus.machine, shift: focus.shift }) : all;
  }, [kpi, filter]);
  const machine = filter?.machine ?? series.data?.machine ?? ALL;
  const shift = filter?.shift ?? series.data?.shift ?? ALL;
  // without the KPI name the series never loads: show the /metrics error instead of an endless skeleton
  const state = metrics.error ? { ...series, error: metrics.error, reload: metrics.reload } : series;

  return (
    <PageBody wide>
      <PageHeader
        title={t.overview.title}
        lead={t.overview.lead}
        right={
          <div className="flex flex-wrap items-center gap-3">
            <Segmented
              label={t.overview.machine}
              value={machine}
              onChange={(m) => setFilter({ machine: m, shift })}
              options={[{ value: ALL, label: t.overview.allMachines }, ...MACHINES.map((m) => ({ value: m, label: m }))]}
            />
            <Segmented
              label={t.overview.shift}
              value={shift}
              onChange={(s) => setFilter({ machine, shift: s })}
              options={[{ value: ALL, label: t.overview.allShifts }, ...SHIFTS.map((s) => ({ value: s, label: shiftLabel(s) }))]}
            />
            <RefreshButton state={state} />
            {/* storyboard S2: the presenter starts the analysis from this screen ("Bấm Phân tích") */}
            <Link href="/?source=live" className={buttonClasses("solid", "sm")} data-testid="overview-analyze">
              <Play className="size-4" />
              {t.overview.analyze}
            </Link>
          </div>
        }
      />
      <DataState
        state={state}
        skeleton={
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-28" />
              ))}
            </div>
            <Skeleton className="h-110" />
          </>
        }
      >
        {(s) => <SeriesView series={s} onFocus={(m, sh) => setFilter({ machine: m, shift: sh })} />}
      </DataState>
    </PageBody>
  );
}
