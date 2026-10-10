import { BookOpenCheck, FileCheck2, Lightbulb, SearchCheck, TrendingDown, Wrench } from "lucide-react";
import { causeLabel, dateTime, groupLabel, isObj, kpiLabel, num, pct, shiftLabel, str, type Obj } from "@/lib/format";
import { t } from "@/lib/strings";
import { Badge, Card } from "@/components/ui/primitives";

function Cell({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted [&>svg]:size-4">
        {icon}
        {title}
      </div>
      <div className="leading-relaxed">{children}</div>
    </div>
  );
}

/** Kaizen / A3 sheet from learning_saved.content (FR-10): problem, cause, action, result, SOP. */
export function KaizenCard({ content, outcome, compact }: { content: Obj; outcome: string; compact?: boolean }) {
  const anomaly = isObj(content.anomaly) ? content.anomaly : {};
  const cause = isObj(content.root_cause) ? content.root_cause : {};
  const ok = outcome === "success";
  return (
    <Card className="p-5 md:p-6" data-testid="kaizen-card">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <BookOpenCheck className="size-6 text-accent" />
        <h3 className="text-xl font-semibold">{t.kaizen.title}</h3>
        <Badge tone={ok ? "ok" : "neutral"} className="ml-auto" data-testid="kaizen-outcome">
          {t.kaizen.outcome[outcome] ?? outcome}
        </Badge>
      </div>
      <div className={compact ? "grid gap-3" : "grid gap-3 md:grid-cols-2"}>
        <Cell icon={<SearchCheck />} title={t.kaizen.problem}>
          <span className="font-semibold">{kpiLabel(anomaly.kpi)}</span> {pct(anomaly.baseline)} → <span className="font-semibold text-bad">{pct(anomaly.value)}</span>
          <div className="text-sm text-muted">
            Máy {str(anomaly.machine)} · {shiftLabel(anomaly.shift)} · {t.anomaly.since} {dateTime(anomaly.start)}
          </div>
        </Cell>
        <Cell icon={<Lightbulb />} title={t.kaizen.cause}>
          <span className="font-semibold">{causeLabel(cause.description)}</span>
          <div className="text-sm text-muted">
            {groupLabel(cause.group)}
            {num(cause.confidence) !== null ? ` · ${Math.round((num(cause.confidence) ?? 0) * 100)}%` : ""}
          </div>
        </Cell>
        <Cell icon={<Wrench />} title={t.kaizen.action}>
          {str(content.change)}
        </Cell>
        <Cell icon={<TrendingDown />} title={t.kaizen.result}>
          <span className="text-bad">{pct(content.kpi_before)}</span> → <span className="font-semibold text-ok">{pct(content.kpi_after)}</span>
          <div className="flex items-center gap-1.5 text-sm text-muted">
            <FileCheck2 className="size-4" />
            {t.kaizen.sop} {str(content.sop_id)} {content.sop_version !== undefined && content.sop_version !== null ? `v${str(content.sop_version)}` : ""}
          </div>
        </Cell>
      </div>
    </Card>
  );
}
