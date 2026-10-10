"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, FileClock, MessageSquare, RotateCcw, ScrollText, Search, Sparkles, XCircle } from "lucide-react";
import { MockBanner } from "@/components/data/MockBanner";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Badge, Card, CardTitle, EmptyState, Input, type Tone } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { clock, dateOnly } from "@/lib/format";
import { auditRows, sopVersions, type AuditRow } from "@/lib/mockData";
import { t } from "@/lib/strings";

function ActionBadge({ row }: { row: AuditRow }) {
  let tone: Tone = "neutral";
  let icon: React.ReactNode = null;
  let label = row.what;
  if (row.kind === "decision") {
    const kind = row.what === "rollback" ? "rollback" : row.what === "halt" ? "dừng" : "đề xuất";
    label = `${t.decisions[row.decision ?? ""] ?? row.decision} ${kind}`;
    tone = row.decision === "approved" ? "ok" : row.decision === "rejected" ? "bad" : "wait";
    icon = row.decision === "approved" ? <CheckCircle2 className="size-4" /> : row.decision === "rejected" ? <XCircle className="size-4" /> : null;
  } else if (row.kind === "apply") {
    tone = "accent";
    icon = <FileClock className="size-4" />;
    label = `Áp dụng ${row.what}`;
  } else if (row.kind === "rollback") {
    tone = "bad";
    icon = <RotateCcw className="size-4" />;
    label = `Rollback ${row.what}`;
  } else if (row.kind === "answer") {
    icon = <MessageSquare className="size-4" />;
    label = "Trả lời câu hỏi";
  } else if (row.kind === "learn") {
    tone = "ok";
    icon = <Sparkles className="size-4" />;
    label = "Lưu bài học";
  }
  return (
    <Badge tone={tone}>
      {icon}
      {label}
    </Badge>
  );
}

export default function AuditPage() {
  const rows = useMemo(() => auditRows(), []);
  const versions = useMemo(() => sopVersions(), []);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(versions[0] ? `${versions[0].sop_id}-${versions[0].version}` : null);
  const filtered = rows.filter((r) => `${r.who} ${r.what} ${r.detail} ${r.run_id}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <PageBody wide>
      <PageHeader title={t.audit.title} lead={t.audit.lead} />
      <MockBanner />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(22rem,1fr)]">
        <Card className="overflow-hidden">
          <div className="flex items-center gap-3 border-b border-border p-4">
            <ScrollText className="size-5 text-muted" />
            <h2 className="font-semibold">Nhật ký (audit_log)</h2>
            <div className="relative ml-auto w-full max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <Input className="h-9 pl-9 text-sm" placeholder="Tìm…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Tìm trong nhật ký" />
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
                  {filtered.map((r) => (
                    <tr key={r.id} className="align-top" data-testid="audit-row">
                      <td className="whitespace-nowrap px-4 py-2.5 text-sm tabular-nums text-muted">
                        {dateOnly(r.ts)} {clock(r.ts)}
                        <div className="text-xs">
                          <code>{r.run_id}</code>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 font-medium">{r.who}</td>
                      <td className="px-4 py-2.5">
                        <ActionBadge row={r} />
                      </td>
                      <td className="px-4 py-2.5 text-sm text-muted">{r.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <CardTitle icon={<FileClock />}>{t.audit.versions}</CardTitle>
          {versions.length === 0 ? (
            <EmptyState>{t.audit.empty}</EmptyState>
          ) : (
            <ol className="relative mt-4 space-y-3 border-l-2 border-border pl-5">
              {versions.map((v) => {
                const key = `${v.sop_id}-${v.version}`;
                const isOpen = open === key;
                return (
                  <li key={key} className="relative" data-testid="sop-version">
                    <span
                      className={cn(
                        "absolute -left-[1.72rem] top-1.5 size-3 rounded-full border-2 border-surface",
                        v.kind === "rollback" ? "bg-bad" : "bg-accent",
                      )}
                    />
                    <button className="w-full text-left" onClick={() => setOpen(isOpen ? null : key)} aria-expanded={isOpen}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">
                          {v.sop_id} v{v.version}
                        </span>
                        <Badge tone={v.kind === "rollback" ? "bad" : "accent"}>
                          {v.kind === "rollback" ? t.audit.restored(v.version, v.previous ?? 0) : t.audit.applied(v.version)}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted">
                        {v.approved_by} · {dateOnly(v.ts)} {clock(v.ts)} · <code>{v.run_id}</code>
                      </div>
                    </button>
                    {isOpen && (
                      <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-surface-2 p-3 font-mono text-sm leading-relaxed">{v.content || t.common.noData}</pre>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </Card>
      </div>
    </PageBody>
  );
}
