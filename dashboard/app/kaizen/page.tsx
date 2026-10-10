"use client";

import { ArrowDownRight, ArrowUpRight, BookOpenCheck, Clock3, Repeat2, ShieldAlert } from "lucide-react";
import { DataState, RefreshButton } from "@/components/data/DataState";
import { KaizenCard } from "@/components/run/KaizenCard";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Badge, Card, EmptyState, Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { fmtNum, kpiLabel, pct } from "@/lib/format";
import { getMetrics, listLessons, metricChange, type Metric } from "@/lib/readApi";
import { t } from "@/lib/strings";
import { useApi } from "@/lib/useApi";

const FIXED: Record<string, { label: string; icon: React.ReactNode }> = {
  mttd_mttr: { label: t.kaizenPage.mttdMttr, icon: <Clock3 /> },
  recurrence_rate: { label: t.kaizenPage.recurrence, icon: <Repeat2 /> },
};

/** The first metric is the main KPI of the domain config; the other two have fixed names (payloads.md). */
function meta(m: Metric) {
  return FIXED[m.name] ?? { label: kpiLabel(m.name), icon: <ShieldAlert /> };
}

function value(m: Metric, v: number | null) {
  if (m.unit === "ratio") return pct(v);
  if (m.unit === "hours") return `${fmtNum(v)} ${t.kaizenPage.hours}`;
  return `${fmtNum(v)} ${m.unit}`;
}

function MetricCard({ m }: { m: Metric }) {
  const { label, icon } = meta(m);
  const change = metricChange(m);
  if (change === null) {
    return (
      <Card className="border-dashed p-5" data-testid="metric-card" title={m.reason ?? undefined}>
        <div className="flex items-center gap-2 text-sm font-semibold text-muted [&>svg]:size-4">
          {icon}
          {label}
        </div>
        <div className="mt-3 text-xl font-semibold text-muted" data-testid="metric-unavailable">
          {t.kaizenPage.unavailable}
        </div>
        <p className="mt-1 text-sm text-muted">{FIXED[m.name] ? t.kaizenPage.noSource : t.kaizenPage.noLesson}</p>
      </Card>
    );
  }
  // all three metrics are "lower is better" (defect-like KPI, hours, recurrence); /metrics carries no direction
  const better = change <= 0;
  return (
    <Card className="p-5" data-testid="metric-card">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted [&>svg]:size-4">
        {icon}
        {label}
      </div>
      <div className="mt-3 flex items-end gap-3">
        <span className={cn("text-3xl font-bold tabular-nums tracking-tight", better ? "text-ok" : "text-bad")}>{value(m, m.after)}</span>
        <Badge tone={better ? "ok" : "bad"} className="mb-1">
          {better ? <ArrowDownRight className="size-4" /> : <ArrowUpRight className="size-4" />}
          {Math.round(Math.abs(change) * 100)}%
        </Badge>
      </div>
      <div className="mt-1 text-sm text-muted">
        {t.kaizenPage.beforeAgent}: <span className="tabular-nums">{value(m, m.before)}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <div className={cn("h-full rounded-full", better ? "bg-ok" : "bg-bad")} style={{ width: `${Math.min(100, Math.max(4, (1 + change) * 100))}%` }} />
      </div>
      {m.run_id && <div className="mt-2 text-xs text-muted">{t.kaizenPage.fromRun(m.run_id)}</div>}
    </Card>
  );
}

export default function KaizenPage() {
  const metrics = useApi(() => getMetrics(), []);
  const lessons = useApi(() => listLessons(), []);
  const refresh = {
    loading: metrics.loading || lessons.loading,
    reload: () => {
      metrics.reload();
      lessons.reload();
    },
  };
  return (
    <PageBody wide>
      <PageHeader title={t.kaizenPage.title} lead={t.kaizenPage.lead} right={<RefreshButton state={refresh} />} />
      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t.kaizenPage.metrics}</h2>
        <DataState
          state={metrics}
          skeleton={
            <div className="grid gap-4 md:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-40" />
              ))}
            </div>
          }
        >
          {(list) => (
            <div className="grid gap-4 md:grid-cols-3">
              {list.map((m) => (
                <MetricCard key={m.name} m={m} />
              ))}
            </div>
          )}
        </DataState>
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">{t.kaizenPage.cards}</h2>
        <DataState state={lessons}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState icon={<BookOpenCheck />}>{t.kaizen.empty}</EmptyState>
            ) : (
              <div className="grid gap-5 2xl:grid-cols-2">
                {list.map((e) => (
                  <div key={`${e.run_id}-${e.ts}`}>
                    <div className="mb-1 text-sm text-muted">
                      <code>{e.run_id}</code>
                    </div>
                    <KaizenCard content={e.content} outcome={e.outcome} />
                  </div>
                ))}
              </div>
            )
          }
        </DataState>
      </section>
    </PageBody>
  );
}
