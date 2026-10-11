"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Eye, History, Play, ScrollText, Search } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import { DataState, RefreshButton } from "@/components/data/DataState";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Badge, Button, buttonClasses, Card, EmptyState, Input, type Tone } from "@/components/ui/primitives";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { dateTime } from "@/lib/format";
import { listRuns, type RunSummary } from "@/lib/readApi";
import { t } from "@/lib/strings";
import { useApi } from "@/lib/useApi";

const OUTCOME: Record<string, { label: string; tone: Tone }> = {
  completed: { label: t.status.completed, tone: "ok" },
  closed: { label: t.status.closed, tone: "run" },
  no_anomaly: { label: t.status.noAnomaly, tone: "ok" },
  error: { label: t.status.error, tone: "bad" },
};

function runResult(r: RunSummary): { label: string; tone: Tone } {
  if (r.state === "error") return OUTCOME.error;
  if (r.state === "running") return { label: t.status.running, tone: "run" };
  if (r.state === "waiting") {
    if (r.pending?.type === "answer") return { label: t.status.waitAnswer, tone: "wait" };
    if (r.pending?.kind === "halt") return { label: t.status.halted, tone: "wait" };
    if (r.pending?.kind === "rollback") return { label: t.status.waitRollback, tone: "wait" };
    return { label: t.status.waitApproval, tone: "wait" };
  }
  return OUTCOME[r.outcome ?? ""] ?? { label: t.status.completedNoLearn, tone: "neutral" };
}

// secondary columns drop on small screens so the open button never needs a sideways scroll
const HIDE_BELOW_MD = "hidden md:table-cell";
const HIDE_BELOW_LG = "hidden lg:table-cell";

function duration(r: RunSummary): string {
  if (!r.finished_at) return t.common.none;
  const s = Math.max(0, Math.round((Date.parse(r.finished_at) - Date.parse(r.started_at)) / 1000));
  return Number.isNaN(s) ? t.common.none : s < 60 ? t.runs.seconds(s) : t.runs.minutes(Math.round(s / 60));
}

/** A run that still needs a person opens in live mode; a finished one opens read-only. */
function openLink(r: RunSummary) {
  return r.state === "finished"
    ? { href: `/?source=sse&run=${encodeURIComponent(r.run_id)}`, label: t.runs.view, icon: <Eye className="size-4" /> }
    : { href: `/?source=live&run=${encodeURIComponent(r.run_id)}`, label: t.runs.continue, icon: <Play className="size-4" /> };
}

function RunsTable({ all }: { all: RunSummary[] }) {
  const [q, setQ] = useState("");
  const [size, setSize] = useState(10);
  const [page, setPage] = useState(0);
  const rows = all.filter((r) => `${r.run_id} ${runResult(r).label}`.toLowerCase().includes(q.toLowerCase()));
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const shown = rows.slice(page * size, page * size + size);

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder={t.runs.search}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(0);
            }}
            aria-label={t.runs.search}
          />
        </div>
      </div>
      {shown.length === 0 ? (
        <EmptyState
          icon={<History />}
          action={
            all.length === 0 && (
              <Link href="/?source=live" className={buttonClasses("solid", "md")}>
                <Play className="size-4" />
                {t.runs.startFirst}
              </Link>
            )
          }
        >
          {all.length === 0 ? t.runs.none : t.runs.empty}
        </EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-surface-2 text-sm text-muted">
              <tr>
                <th className="px-3 py-3 md:px-4 font-semibold">{t.runs.columns.id}</th>
                <th className="px-3 py-3 md:px-4 font-semibold">{t.runs.columns.result}</th>
                <th className={cn("px-3 py-3 md:px-4 font-semibold", HIDE_BELOW_MD)}>{t.runs.columns.started}</th>
                <th className={cn("px-3 py-3 md:px-4 font-semibold", HIDE_BELOW_LG)}>{t.runs.columns.duration}</th>
                <th className="px-3 py-3 md:px-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {shown.map((r) => {
                const res = runResult(r);
                const link = openLink(r);
                return (
                  <tr key={r.run_id} className="transition hover:bg-surface-2/60" data-testid="run-row">
                    <td className="px-3 py-3 md:px-4">
                      <code className="text-xs sm:text-sm">{r.run_id}</code>
                    </td>
                    <td className="px-3 py-3 md:px-4">
                      <Badge tone={res.tone}>{res.label}</Badge>
                    </td>
                    <td className={cn("whitespace-nowrap px-3 py-3 md:px-4 text-sm text-muted tabular-nums", HIDE_BELOW_MD)}>{dateTime(r.started_at)}</td>
                    <td className={cn("whitespace-nowrap px-3 py-3 md:px-4 text-sm text-muted tabular-nums", HIDE_BELOW_LG)}>{duration(r)}</td>
                    <td className="px-3 py-3 md:px-4">
                      <div className="flex items-center justify-end gap-1.5">
                        <Tooltip content={t.runs.audit} side="top">
                          <Link
                            href={`/audit?run=${encodeURIComponent(r.run_id)}`}
                            className={buttonClasses("ghost", "sm", "hidden px-2 sm:inline-flex")}
                            aria-label={t.runs.audit}
                          >
                            <ScrollText className="size-4" />
                          </Link>
                        </Tooltip>
                        {/* icon only on phones so the row fits without a sideways scroll */}
                        <Link href={link.href} className={buttonClasses(r.state === "finished" ? "outline" : "solid", "sm")} aria-label={link.label}>
                          {link.icon}
                          <span className="hidden sm:inline">{link.label}</span>
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex items-center justify-end gap-3 border-t border-border px-3 py-3 md:px-4 text-sm text-muted">
        <span>{t.runs.pageSize}</span>
        <Select
          value={String(size)}
          onValueChange={(v) => {
            setSize(Number(v));
            setPage(0);
          }}
        >
          <SelectTrigger size="sm" className="w-20" aria-label={t.runs.pageSize}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[5, 10, 25].map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="tabular-nums">
          {page + 1} / {pages}
        </span>
        <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label={t.runs.prev}>
          <ChevronLeft className="size-4" />
        </Button>
        <Button size="sm" variant="outline" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label={t.runs.next}>
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </Card>
  );
}

export default function RunsPage() {
  const runs = useApi(() => listRuns(), []);
  return (
    <PageBody>
      <PageHeader title={t.runs.title} lead={t.runs.lead} right={<RefreshButton state={runs} />} />
      <DataState state={runs}>{(all) => <RunsTable all={all} />}</DataState>
    </PageBody>
  );
}
