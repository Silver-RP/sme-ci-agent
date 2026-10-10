"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, History, Play, Search } from "lucide-react";
import { MockBanner } from "@/components/data/MockBanner";
import { PageBody, PageHeader } from "@/components/shell/AppShell";
import { Badge, Button, buttonClasses, Card, EmptyState, Input, Select, type Tone } from "@/components/ui/primitives";
import { clock, dateOnly } from "@/lib/format";
import { runRows } from "@/lib/mockData";
import { t } from "@/lib/strings";

const RESULT: Record<string, { label: string; tone: Tone }> = {
  completed: { label: t.status.completed, tone: "ok" },
  closed: { label: t.status.closed, tone: "run" },
  no_anomaly: { label: t.status.noAnomaly, tone: "ok" },
  error: { label: t.status.error, tone: "bad" },
  halt: { label: t.status.halted, tone: "wait" },
  answer: { label: t.status.waitAnswer, tone: "wait" },
  approval: { label: t.status.waitApproval, tone: "wait" },
};

export default function RunsPage() {
  const all = useMemo(() => runRows(), []);
  const [q, setQ] = useState("");
  const [size, setSize] = useState(10);
  const [page, setPage] = useState(0);
  const rows = all.filter((r) => `${r.run_id} ${r.name} ${t.replay.files[r.name] ?? ""}`.toLowerCase().includes(q.toLowerCase()));
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const shown = rows.slice(page * size, page * size + size);

  return (
    <PageBody>
      <PageHeader title={t.runs.title} lead={t.runs.lead} />
      <MockBanner />
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
          <EmptyState icon={<History />}>{t.runs.empty}</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-surface-2 text-sm text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">{t.runs.columns.id}</th>
                  <th className="px-4 py-3 font-semibold">{t.runs.columns.branch}</th>
                  <th className="px-4 py-3 font-semibold">{t.runs.columns.result}</th>
                  <th className="px-4 py-3 text-right font-semibold">{t.runs.columns.events}</th>
                  <th className="px-4 py-3 font-semibold">{t.runs.columns.when}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {shown.map((r) => {
                  const res = RESULT[r.result] ?? { label: r.result, tone: "neutral" as Tone };
                  return (
                    <tr key={r.name} className="transition hover:bg-surface-2/60" data-testid="run-row">
                      <td className="px-4 py-3">
                        <code className="text-sm">{r.run_id}</code>
                      </td>
                      <td className="px-4 py-3">{t.replay.files[r.name] ?? r.name}</td>
                      <td className="px-4 py-3">
                        <Badge tone={res.tone}>{res.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.events}</td>
                      <td className="px-4 py-3 text-sm text-muted tabular-nums">
                        {dateOnly(r.ts)} {clock(r.ts)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link href={`/?source=fixture&file=${r.name}`} className={buttonClasses("outline", "sm")}>
                          <Play className="size-4" />
                          {t.runs.open}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-end gap-3 border-t border-border px-4 py-3 text-sm text-muted">
          <span>Số dòng</span>
          <Select
            className="h-8 w-20 text-sm"
            value={size}
            onChange={(e) => {
              setSize(Number(e.target.value));
              setPage(0);
            }}
            aria-label="Số dòng mỗi trang"
          >
            {[5, 10, 25].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Select>
          <span className="tabular-nums">
            {page + 1} / {pages}
          </span>
          <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Trang trước">
            <ChevronLeft className="size-4" />
          </Button>
          <Button size="sm" variant="outline" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Trang sau">
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </Card>
    </PageBody>
  );
}
