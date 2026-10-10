"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BookOpen, CheckCircle2, CircleStop, FileClock, Gauge, MessageSquare, PauseCircle, Scale, ScrollText, Search, Sparkles, X, XCircle } from "lucide-react";
import { DataState, RefreshButton } from "@/components/data/DataState";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Badge, Card, CardTitle, EmptyState, Input, type Tone } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { describeAudit, type AuditIcon } from "@/lib/describe";
import { dateTime } from "@/lib/format";
import { describeVersions, listAudit, listSopVersions, sopIdsOf, type AuditRow, type VersionOrigin } from "@/lib/readApi";
import { t } from "@/lib/strings";
import { useApi } from "@/lib/useApi";

const AUDIT_LIMIT = 200;

const ICONS: Record<AuditIcon, React.ReactNode> = {
  approve: <CheckCircle2 className="size-4" />,
  reject: <XCircle className="size-4" />,
  decide: <Scale className="size-4" />,
  answer: <MessageSquare className="size-4" />,
  sop: <FileClock className="size-4" />,
  learn: <Sparkles className="size-4" />,
  measure: <Gauge className="size-4" />,
  halt: <PauseCircle className="size-4" />,
  close: <CircleStop className="size-4" />,
  read: <BookOpen className="size-4" />,
};

/** Role words for the backend's generic actors; approver names stay as they are. */
const actorLabel = (actor: string) => t.audit.actors[actor] ?? actor;

function AuditTable({ rows }: { rows: AuditRow[] }) {
  const [q, setQ] = useState("");
  const [showReads, setShowReads] = useState(false);
  const views = rows.map((r) => ({ row: r, view: describeAudit(r.action, r.params) }));
  const filtered = views.filter(
    ({ row, view }) =>
      (showReads || view.group !== "read") &&
      `${actorLabel(row.actor)} ${view.label} ${view.detail} ${row.run_id ?? ""}`.toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <ScrollText className="size-5 text-muted" />
        <h2 className="font-semibold">{t.audit.log}</h2>
        <span className="text-sm text-muted">{t.audit.latest(AUDIT_LIMIT)}</span>
        <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm text-muted">
          <input type="checkbox" className="size-4 accent-accent" checked={showReads} onChange={(e) => setShowReads(e.target.checked)} />
          {t.audit.showReads}
        </label>
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="h-9 pl-9 text-sm" placeholder={t.audit.search} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t.audit.searchLabel} />
        </div>
      </div>
      {filtered.length === 0 ? (
        <EmptyState icon={<ScrollText />}>{t.audit.empty}</EmptyState>
      ) : (
        <div className="max-h-[70vh] overflow-auto">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-surface-2 text-sm text-muted">
              <tr>
                <th className="px-4 py-2.5 font-semibold">{t.audit.when}</th>
                <th className="px-4 py-2.5 font-semibold">{t.audit.who}</th>
                <th className="px-4 py-2.5 font-semibold">{t.audit.what}</th>
                <th className="px-4 py-2.5 font-semibold">{t.audit.detail}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map(({ row, view }) => (
                <tr key={row.id} className="align-top" data-testid="audit-row">
                  <td className="whitespace-nowrap px-4 py-2.5 text-sm tabular-nums text-muted">
                    {dateTime(row.ts)}
                    {row.run_id && (
                      <div className="text-xs">
                        <code>{row.run_id}</code>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-medium">{actorLabel(row.actor)}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={view.tone as Tone}>
                      {ICONS[view.icon]}
                      {view.label}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-muted">{view.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function originBadge(origin: VersionOrigin, version: number): { label: string; tone: Tone } {
  if (origin.kind === "config") return { label: t.audit.original, tone: "neutral" };
  if (origin.kind === "restored") return { label: t.audit.restoredContent(origin.from), tone: "bad" };
  return { label: t.audit.applied(version), tone: "accent" };
}

type SopHistory = { sop_id: string; versions: ReturnType<typeof describeVersions> };

function SopVersions({ sops }: { sops: SopHistory[] }) {
  const first = sops[0]?.versions[0];
  const [open, setOpen] = useState<string | null>(first ? `${sops[0].sop_id}-${first.version}` : null);
  if (sops.length === 0) return <EmptyState>{t.audit.noSop}</EmptyState>;
  return (
    <div className="mt-4 space-y-6">
      {sops.map(({ sop_id, versions }) => (
        <div key={sop_id}>
          {sops.length > 1 && <h3 className="mb-2 font-semibold">{sop_id}</h3>}
          <ol className="relative space-y-3 border-l-2 border-border pl-5">
            {versions.map((v) => {
              const key = `${sop_id}-${v.version}`;
              const isOpen = open === key;
              const badge = originBadge(v.origin, v.version);
              return (
                <li key={key} className="relative" data-testid="sop-version">
                  <span
                    className={cn(
                      "absolute left-[-1.72rem] top-1.5 size-3 rounded-full border-2 border-surface",
                      v.origin.kind === "restored" ? "bg-bad" : v.origin.kind === "config" ? "bg-muted" : "bg-accent",
                    )}
                  />
                  <button className="w-full rounded-md text-left transition active:bg-surface-2" onClick={() => setOpen(isOpen ? null : key)} aria-expanded={isOpen}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">
                        {sop_id} v{v.version}
                      </span>
                      <Badge tone={badge.tone}>{badge.label}</Badge>
                    </div>
                    {v.origin.kind !== "config" && (
                      <div className="text-sm text-muted">
                        {t.audit.approvedBy(v.created_by)} · {dateTime(v.created_at)}
                        {v.run_id && (
                          <>
                            {" "}
                            · <code>{v.run_id}</code>
                          </>
                        )}
                      </div>
                    )}
                  </button>
                  {isOpen && <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-surface-2 p-3 font-mono text-sm leading-relaxed">{v.content || t.common.noData}</pre>}
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </div>
  );
}

// useSearchParams needs a Suspense boundary for the static build
export default function AuditPage() {
  return (
    <Suspense>
      <AuditContent />
    </Suspense>
  );
}

function AuditContent() {
  // ?run=<id>: opened from a run ("Xem nhật ký của run"); the API filters by run_id
  const runFilter = useSearchParams().get("run");
  const audit = useApi(() => listAudit(AUDIT_LIMIT, runFilter), [runFilter]);
  // reloaded with the log: a run that moved on may have written a new SOP version
  const sops = useApi(async (): Promise<SopHistory[] | null> => {
    if (!audit.data) return null;
    return Promise.all(sopIdsOf(audit.data).map(async (id) => ({ sop_id: id, versions: describeVersions(await listSopVersions(id)) })));
  }, [audit.data]);
  const refresh = { loading: audit.loading || sops.loading, reload: audit.reload };

  return (
    <PageBody wide>
      <PageHeader title={t.audit.title} lead={t.audit.lead} right={<RefreshButton state={refresh} />} />
      {runFilter && (
        <div className="mb-4 flex items-center gap-2 text-sm" data-testid="run-filter">
          <span className="text-muted">{t.audit.filteredBy}</span>
          <code className="rounded-md bg-surface-2 px-2 py-0.5">{runFilter}</code>
          <Link href="/audit" className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-semibold text-accent hover:bg-accent-soft active:bg-accent-soft">
            <X className="size-4" />
            {t.audit.clearFilter}
          </Link>
        </div>
      )}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(22rem,1fr)]">
        <DataState state={audit}>{(rows) => <AuditTable rows={rows} />}</DataState>
        <Card className="p-5">
          <CardTitle icon={<FileClock />}>{t.audit.versions}</CardTitle>
          <DataState state={sops}>{(list) => <SopVersions sops={list} />}</DataState>
        </Card>
      </div>
    </PageBody>
  );
}
