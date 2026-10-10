"use client";

import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dateOnly, dateTime, pct } from "@/lib/format";
import type { KpiSeries } from "@/lib/mockData";
import { t } from "@/lib/strings";

/**
 * One KPI over time (S2, FR-09): a single series (no legend box, the card title names it), the baseline
 * and the upper control limit as reference lines, Detect's anomalies as tinted bands, planned
 * maintenance as a neutral band. Crosshair tooltip on hover.
 */
export function KpiChart({ series, height = 380 }: { series: KpiSeries; height?: number }) {
  const data = series.points.map((p) => ({ ts: p.ts, value: p.value }));
  const first = data[0]?.ts ?? "";
  const last = data.at(-1)?.ts ?? "";
  const clamp = (s: string) => (s < first ? first : s > last ? last : s);
  const nearest = (s: string) => data.find((d) => d.ts >= clamp(s))?.ts ?? last;
  return (
    <div style={{ height }} data-testid="kpi-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="ts"
            tickFormatter={(v: string) => dateOnly(v).slice(0, 5)}
            minTickGap={48}
            stroke="var(--muted)"
            tick={{ fill: "var(--muted)", fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            tickFormatter={(v: number) => pct(v, 0)}
            width={52}
            stroke="var(--muted)"
            tick={{ fill: "var(--muted)", fontSize: 13 }}
            tickLine={false}
            axisLine={false}
            domain={[0, (max: number) => Math.max(0.08, Math.ceil(max * 100) / 100)]}
          />
          {series.planned.map((a) => (
            <ReferenceArea key={`p-${a.start}`} x1={nearest(a.start)} x2={nearest(a.end)} fill="var(--run)" fillOpacity={0.12} ifOverflow="hidden" />
          ))}
          {series.anomalies.map((a) => (
            <ReferenceArea
              key={`a-${a.start}`}
              x1={nearest(a.start)}
              x2={nearest(a.end)}
              fill="var(--bad)"
              fillOpacity={0.1}
              ifOverflow="hidden"
              label={{ value: t.overview.anomaly, position: "insideTopLeft", fill: "var(--bad)", fontSize: 13, fontWeight: 600 }}
            />
          ))}
          <ReferenceLine
            y={series.baseline}
            stroke="var(--muted)"
            strokeDasharray="4 4"
            label={{ value: `${t.overview.baseline} ${pct(series.baseline)}`, position: "insideBottomRight", fill: "var(--muted)", fontSize: 13 }}
          />
          <ReferenceLine
            y={series.upper_limit}
            stroke="var(--bad)"
            strokeDasharray="6 4"
            label={{ value: `${t.overview.limit} ${pct(series.upper_limit)}`, position: "insideTopRight", fill: "var(--bad)", fontSize: 13 }}
          />
          <Tooltip
            cursor={{ stroke: "var(--muted)", strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as { ts: string; value: number };
              const over = p.value > series.upper_limit;
              return (
                <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm shadow-card">
                  <div className="text-muted">{dateTime(p.ts)}</div>
                  <div className="font-semibold tabular-nums">
                    {t.overview.value}: {pct(p.value, 2)}
                  </div>
                  {over && <div className="font-semibold text-bad">↑ {t.overview.limit}</div>}
                </div>
              );
            }}
          />
          <Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
