"use client";

import { useState } from "react";
import { RunControls } from "@/components/RunControls";
import { RunView } from "@/components/RunView";
import type { ApiOptions, RunStatus } from "@/lib/api";
import { createSseSource, type EventSourceCtor } from "@/lib/sources";

/** Real backend: start a run, follow its SSE, answer questions, decide approvals. */
export function LiveRun({ api, ctor }: { api?: ApiOptions; ctor?: EventSourceCtor }) {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const runId = status?.run_id ?? null;
  return (
    <RunView
      title={runId ? `Run ${runId} (live)` : "New run (live backend)"}
      sourceKey={`live:${runId ?? ""}`}
      makeSource={() => (runId ? createSseSource(runId, { baseUrl: api?.baseUrl, ctor }) : null)}
      controls={<RunControls runId={runId} status={status} onStarted={setStatus} onStatus={setStatus} api={api} />}
    />
  );
}
