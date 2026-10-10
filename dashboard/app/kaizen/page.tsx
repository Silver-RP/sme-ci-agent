"use client";

import { useMemo } from "react";
import { ArrowDownRight, BookOpenCheck, Clock3, Repeat2, ShieldAlert, Wrench } from "lucide-react";
import { MockBanner } from "@/components/data/MockBanner";
import { KaizenCard } from "@/components/run/KaizenCard";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Badge, Card, EmptyState } from "@/components/ui/primitives";
import { fmtNum, pct } from "@/lib/format";
import { kaizenEntries, MOCK_METRICS, type Metric } from "@/lib/mockData";
import { t } from "@/lib/strings";

const META: Record<Metric["key"], { label: string; icon: React.ReactNode }> = {
  defect: { label: t.kaizenPage.defect, icon: <ShieldAlert /> },
  mttd: { label: t.kaizenPage.mttd, icon: <Clock3 /> },
  mttr: { label: t.kaizenPage.mttr, icon: <Wrench /> },
  recurrence: { label: t.kaizenPage.recurrence, icon: <Repeat2 /> },
};

function value(m: Metric, v: number) {
  return m.unit === "ratio" ? pct(v) : `${fmtNum(v)} giờ`;
}

function MetricCard({ m }: { m: Metric }) {
  const change = m.before === 0 ? 0 : (m.after - m.before) / m.before;
  return (
    <Card className="p-5" data-testid="metric-card">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted [&>svg]:size-4">
        {META[m.key].icon}
        {META[m.key].label}
      </div>
      <div className="mt-3 flex items-end gap-3">
        <span className="text-4xl font-bold tabular-nums tracking-tight text-ok">{value(m, m.after)}</span>
        <Badge tone="ok" className="mb-1">
          <ArrowDownRight className="size-4" />
          {Math.round(Math.abs(change) * 100)}%
        </Badge>
      </div>
      <div className="mt-1 text-sm text-muted">
        {t.kaizenPage.beforeAgent}: <span className="tabular-nums">{value(m, m.before)}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <div className="h-full rounded-full bg-ok" style={{ width: `${Math.max(4, (m.after / m.before) * 100)}%` }} />
      </div>
    </Card>
  );
}

export default function KaizenPage() {
  const entries = useMemo(() => kaizenEntries(), []);
  return (
    <PageBody wide>
      <PageHeader title={t.kaizenPage.title} lead={t.kaizenPage.lead} />
      <section className="mb-8">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-xl font-semibold">{t.kaizenPage.metrics}</h2>
          <Badge tone="wait">{t.kaizenPage.pending}</Badge>
        </div>
        <MockBanner text={`${t.source.mockBanner} ${t.kaizenPage.pending}.`} />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {MOCK_METRICS.map((m) => (
            <MetricCard key={m.key} m={m} />
          ))}
        </div>
      </section>
      <section>
        <h2 className="mb-3 text-xl font-semibold">{t.kaizenPage.cards}</h2>
        {entries.length === 0 ? (
          <EmptyState icon={<BookOpenCheck />}>{t.kaizen.empty}</EmptyState>
        ) : (
          <div className="grid gap-5 2xl:grid-cols-2">
            {entries.map((e) => (
              <div key={`${e.run_id}-${e.ts}`}>
                <div className="mb-1 text-sm text-muted">
                  <code>{e.run_id}</code>
                </div>
                <KaizenCard content={e.content} outcome={e.outcome} />
              </div>
            ))}
          </div>
        )}
      </section>
    </PageBody>
  );
}
