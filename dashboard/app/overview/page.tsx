"use client";

import { useMemo, useState } from "react";
import { Activity, Gauge, Siren, TrendingUp } from "lucide-react";
import { KpiChart } from "@/components/data/KpiChart";
import { MockBanner } from "@/components/data/MockBanner";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Card, CardTitle } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { kpiLabel, pct, shiftLabel } from "@/lib/format";
import { MACHINES, mockKpiSeries, SHIFTS } from "@/lib/mockData";
import { t } from "@/lib/strings";

function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-lg bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn("rounded-md px-3 py-1 text-sm font-semibold transition", value === o.value ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg")}
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
      <div className={cn("mt-2 text-4xl font-bold tabular-nums tracking-tight", tone === "bad" && "text-bad", tone === "ok" && "text-ok")}>{value}</div>
    </Card>
  );
}

export default function OverviewPage() {
  const [machine, setMachine] = useState("M02");
  const [shift, setShift] = useState<string>("all");
  const series = useMemo(() => mockKpiSeries(machine, shift === "all" ? null : shift), [machine, shift]);
  const recent = series.points.slice(-7);
  const recentMean = recent.reduce((a, p) => a + p.value, 0) / Math.max(1, recent.length);

  return (
    <PageBody wide>
      <PageHeader
        title={t.overview.title}
        lead={t.overview.lead}
        right={
          <div className="flex flex-wrap gap-3">
            <Segmented label={t.overview.machine} value={machine} onChange={setMachine} options={MACHINES.map((m) => ({ value: m, label: m }))} />
            <Segmented
              label={t.overview.shift}
              value={shift}
              onChange={setShift}
              options={[{ value: "all", label: t.overview.allShifts }, ...SHIFTS.map((s) => ({ value: s, label: shiftLabel(s) }))]}
            />
          </div>
        }
      />
      <MockBanner />
      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<Activity />} label={t.overview.stats.current} value={pct(recentMean)} tone={recentMean > series.upper_limit ? "bad" : "ok"} />
        <Stat icon={<Gauge />} label={t.overview.stats.baseline} value={pct(series.baseline)} />
        <Stat icon={<TrendingUp />} label={t.overview.stats.limit} value={pct(series.upper_limit)} />
        <Stat icon={<Siren />} label={t.overview.stats.anomalies} value={String(series.anomalies.length)} tone={series.anomalies.length ? "bad" : "ok"} />
      </div>
      <Card className="p-5">
        <CardTitle>
          {kpiLabel(series.kpi)} · {t.overview.machine} {machine} · {shift === "all" ? t.overview.allShifts : shiftLabel(shift)}
        </CardTitle>
        <div className="mt-4">
          <KpiChart series={series} />
        </div>
      </Card>
    </PageBody>
  );
}
