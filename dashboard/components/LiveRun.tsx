"use client";

import { useEffect, useState } from "react";
import { RunControls } from "@/components/RunControls";
import { RunView } from "@/components/RunView";
import { fetchApprovers, type ApiOptions, type RunStatus } from "@/lib/api";
import { createSseSource, type EventSourceCtor } from "@/lib/sources";

/** Real backend: start a run, follow its SSE, answer questions, decide approvals. */
export function LiveRun({ api, ctor }: { api?: ApiOptions; ctor?: EventSourceCtor }) {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [approvers, setApprovers] = useState<string[]>([]);
  const runId = status?.run_id ?? null;
  const pendingType = status?.pending?.type;
  const baseUrl = api?.baseUrl;

  // load the allow-list once an approval is needed (a failed call just leaves the datalist empty)
  useEffect(() => {
    if (pendingType !== "approval") return;
    let live = true;
    // global fetch on purpose: a test's injected fetchFn counts run actions, not this read-only lookup
    void fetchApprovers({ baseUrl }).then((a) => {
      if (live) setApprovers(a);
    });
    return () => {
      live = false;
    };
  }, [pendingType, baseUrl]);

  return (
    <RunView
      title={runId ? `Run ${runId} (live)` : "New run (live backend)"}
      sourceKey={`live:${runId ?? ""}`}
      makeSource={() => (runId ? createSseSource(runId, { baseUrl: api?.baseUrl, ctor }) : null)}
      controls={
        <RunControls runId={runId} status={status} onStarted={setStatus} onStatus={setStatus} api={api} approvers={approvers} />
      }
    />
  );
}
