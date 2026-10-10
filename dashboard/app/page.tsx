"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { History, Radio } from "lucide-react";
import { LiveRun } from "@/components/LiveRun";
import { ReplayRun } from "@/components/ReplayRun";
import { RunScreen } from "@/components/run/RunScreen";
import { getRun, type RunStatus } from "@/lib/api";
import { cn } from "@/lib/cn";
import { createSseSource } from "@/lib/sources";
import { t } from "@/lib/strings";
import { useRunEvents } from "@/lib/useRunEvents";

/** Live or replay, one click away (the replay is the stage backup, FR-07). */
function ModeSwitch({ mode }: { mode: "live" | "replay" }) {
  const item = (m: "live" | "replay", href: string, icon: React.ReactNode, label: string) => (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-semibold transition",
        mode === m ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg",
      )}
      aria-current={mode === m ? "page" : undefined}
    >
      {icon}
      {label}
    </Link>
  );
  return (
    <div className="flex rounded-lg bg-surface-2 p-1" data-testid="mode-switch">
      {item("live", "/?source=live", <Radio className="size-4" />, t.source.live)}
      {item("replay", "/?source=fixture", <History className="size-4" />, t.source.replay)}
    </div>
  );
}

/** ?source=sse&run=<id>: follow a run started elsewhere (read-only). */
function WatchRun({ runId }: { runId: string }) {
  const { events, errors, status: connection } = useRunEvents(() => createSseSource(runId), [runId]);
  const [status, setStatus] = useState<RunStatus | null>(null);
  useEffect(() => {
    let live = true;
    getRun(runId)
      .then((s) => live && setStatus(s))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [runId, events.length]);
  const noop = () => undefined;
  return (
    <RunScreen
      mode="watch"
      runId={runId}
      events={events}
      invalidEvents={errors}
      connection={connection}
      status={status}
      busy={false}
      started
      approvers={[]}
      actions={{ answer: noop, decide: noop, retry: noop }}
    />
  );
}

// ?source=live: real backend (&run=<id> picks a run up again). ?source=fixture (default): replay a recording
// (&file=<name> from docs/schema/examples). ?source=sse&run=<id>: follow a run read-only.
function Home() {
  const params = useSearchParams();
  const source = params.get("source") ?? "fixture";
  const run = params.get("run") ?? "";
  if (source === "live") return <LiveRun initialRunId={run || undefined} toolbar={<ModeSwitch mode="live" />} />;
  if (source === "sse" && run) return <WatchRun runId={run} />;
  return <ReplayRun file={params.get("file")} toolbar={<ModeSwitch mode="replay" />} />;
}

export default function Page() {
  return (
    <Suspense fallback={<p className="p-8 text-muted">…</p>}>
      <Home />
    </Suspense>
  );
}
