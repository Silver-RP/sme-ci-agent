import { ArrowDownRight, ArrowRight, ArrowUpRight, CircleAlert, CircleCheck, Hourglass, Target } from "lucide-react";
import { cn } from "@/lib/cn";
import { deltaPts, kpiLabel, num, pct, str, type Obj } from "@/lib/format";
import { t } from "@/lib/strings";
import { Badge } from "@/components/ui/primitives";

/** Result of Measure (FR-03). Never prints null/undefined/passed=. */
export function MeasurementCard({ m, compact }: { m: Obj; compact?: boolean }) {
  const status = str(m.status);
  const kpi = kpiLabel(m.kpi);

  if (status === "insufficient_evidence") {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-wait/40 bg-wait-soft p-4" data-testid="measure-insufficient">
        <Hourglass className="mt-0.5 size-6 shrink-0 text-wait" />
        <div>
          <div className="font-semibold">{t.measure.insufficient}</div>
          <div className="text-muted">
            {kpi} · {t.measure.insufficientDetail(num(m.n_after), num(m.min_samples_after))}
          </div>
        </div>
      </div>
    );
  }
  if (status !== "measured") {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 p-4" data-testid="measure-not-applied">
        <CircleAlert className="mt-0.5 size-6 shrink-0 text-muted" />
        <div>
          <div className="font-semibold">{t.measure.notApplied}</div>
          {str(m.reason) && <div className="text-muted">{str(m.reason)}</div>}
        </div>
      </div>
    );
  }

  const passed = m.passed === true;
  const decrease = str(m.direction) !== "increase";
  const before = num(m.before);
  const after = num(m.after);
  const improved = before !== null && after !== null && (decrease ? after < before : after > before);
  const Arrow = before === null || after === null ? ArrowRight : after < before ? ArrowDownRight : ArrowUpRight;
  const big = compact ? "text-4xl" : "text-6xl";

  return (
    <div data-testid="measure-result" data-passed={passed}>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <span className="font-semibold">{kpi}</span>
        {str(m.machine_id) && <span className="text-muted">· Máy {str(m.machine_id)}</span>}
        <Badge tone={passed ? "ok" : "bad"} className="ml-auto text-base" data-testid="measure-verdict">
          {passed ? <CircleCheck className="size-4" /> : <CircleAlert className="size-4" />}
          {passed ? t.measure.passed : t.measure.failed}
        </Badge>
      </div>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
        <div>
          <div className="text-sm font-semibold uppercase tracking-wide text-muted">{t.measure.before}</div>
          <div className={cn(big, "font-bold tabular-nums tracking-tight text-bad")} data-testid="measure-before">
            {pct(before)}
          </div>
        </div>
        <div className="flex flex-col items-center text-muted">
          <Arrow className={cn(compact ? "size-8" : "size-12", improved ? "text-ok" : "text-bad")} strokeWidth={2.5} />
          <span className="text-sm font-semibold tabular-nums">{deltaPts(before, after)}</span>
        </div>
        <div>
          <div className="text-sm font-semibold uppercase tracking-wide text-muted">{t.measure.after}</div>
          <div className={cn(big, "font-bold tabular-nums tracking-tight", passed ? "text-ok" : "text-bad")} data-testid="measure-after">
            {pct(after)}
          </div>
        </div>
        <div className="border-l border-border pl-6">
          <div className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wide text-muted">
            <Target className="size-4" />
            {t.measure.target}
          </div>
          <div className={cn(compact ? "text-2xl" : "text-3xl", "font-bold tabular-nums")}>{pct(m.target)}</div>
          {num(m.tolerance) !== null && <div className="text-sm text-muted">{t.measure.tolerance(num(m.tolerance) ?? 0)}</div>}
        </div>
      </div>
      <TargetBar before={before} after={after} target={num(m.target)} tolerance={num(m.tolerance)} decrease={decrease} />
      <p className="mt-3 text-sm text-muted" data-testid="measure-samples">
        {t.measure.samples(num(m.n_before), num(m.n_after), num(m.window_days))}
      </p>
    </div>
  );
}

/** One horizontal scale: target band, before and after markers. */
function TargetBar({
  before,
  after,
  target,
  tolerance,
  decrease,
}: {
  before: number | null;
  after: number | null;
  target: number | null;
  tolerance: number | null;
  decrease: boolean;
}) {
  if (before === null || after === null || target === null) return null;
  const max = Math.max(before, after, target) * 1.15 || 1;
  const pos = (v: number) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
  const tol = tolerance ?? 0;
  const lo = decrease ? 0 : target;
  const hi = decrease ? target * (1 + tol) : max;
  return (
    <div className="relative mt-6 h-3 rounded-full bg-surface-2" aria-hidden>
      <div className="absolute inset-y-0 rounded-full bg-ok/25" style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})` }} />
      <div className="absolute -inset-y-1 w-0.5 bg-ok" style={{ left: pos(target) }} />
      <div className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-bad shadow" style={{ left: pos(before) }} />
      <div className="absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-accent shadow" style={{ left: pos(after) }} />
    </div>
  );
}
