"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { RunScreen } from "@/components/run/RunScreen";
import type { RunActions } from "@/components/run/types";
import { answerRun, ApiError, closeRun, decideApproval, fetchApprovers, getRun, retryRun, startRun, type ApiOptions, type RunStatus } from "@/lib/api";
import { createSseSource, type EventSourceCtor } from "@/lib/sources";
import { t } from "@/lib/strings";
import { useRunEvents } from "@/lib/useRunEvents";

function setRunInUrl(runId: string | null) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("source", "live");
    if (runId) url.searchParams.set("run", runId);
    else url.searchParams.delete("run");
    window.history.replaceState(null, "", url.toString());
  } catch {
    /* not in a browser */
  }
}

/**
 * Real backend: start a run, follow its SSE, answer questions, decide approvals, retry a failed step.
 * Nothing is decided automatically: every call follows a click by a person.
 */
export function LiveRun({
  api,
  ctor,
  initialRunId,
  toolbar,
}: {
  api?: ApiOptions;
  ctor?: EventSourceCtor;
  initialRunId?: string;
  toolbar?: ReactNode;
}) {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [approvers, setApprovers] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [pastError, setPastError] = useState<string | null>(null);
  // Bumped only when the stream was really lost: normally it stays open across a retryable error and carries on
  // after Retry by itself (lib/sources.ts, H-46), so the timeline is never cleared.
  const [generation, setGeneration] = useState(0);
  const runId = status?.run_id ?? null;
  const baseUrl = api?.baseUrl;

  const { events, errors, status: connection } = useRunEvents(
    () => (runId ? createSseSource(runId, { baseUrl, ctor }) : null),
    [runId, generation, baseUrl],
  );

  useEffect(() => {
    let live = true;
    // global fetch on purpose: a test's injected fetchFn counts run actions, not this read-only lookup
    void fetchApprovers({ baseUrl }).then((a) => {
      if (live) setApprovers(a);
    });
    return () => {
      live = false;
    };
  }, [baseUrl]);

  // reload with ?run=<id>: pick the run up again
  useEffect(() => {
    if (!initialRunId) return;
    let live = true;
    getRun(initialRunId, api)
      .then((s) => live && setStatus(s))
      .catch((e) => live && setApiError(e instanceof ApiError ? `${e.status || t.error.api}: ${e.message}` : String(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRunId]);

  const run = useCallback(
    async (fn: () => Promise<RunStatus>, done: (s: RunStatus) => void) => {
      setBusy(true);
      setApiError(null);
      try {
        done(await fn());
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && runId) {
          // the run moved on (another tab, a double click): show what it is waiting for now
          setApiError(`409: ${e.message} · ${t.decision.conflict}`);
          try {
            setStatus(await getRun(runId, api));
          } catch {
            /* keep the message above */
          }
        } else {
          setApiError(e instanceof ApiError ? `${e.status || t.error.api}: ${e.message}` : String(e));
        }
      } finally {
        setBusy(false);
      }
    },
    [api, runId],
  );

  const actions: RunActions = {
    start: (changeTime) =>
      void run(
        () => startRun(changeTime, api),
        (s) => {
          setPastError(null);
          setStatus(s);
          setRunInUrl(s.run_id);
        },
      ),
    answer: (text) => runId && void run(() => answerRun(runId, text, api), setStatus),
    decide: (proposalId, kind, d) => runId && void run(() => decideApproval(runId, { proposal_id: proposalId, kind, ...d }, api), setStatus),
    retry: () =>
      runId &&
      void run(
        () => retryRun(runId, api),
        (s) => {
          setPastError(status?.error ?? null);
          setStatus(s);
          if (connection === "disconnected" || connection === "closed") setGeneration((g) => g + 1);
        },
      ),
    close: (closedBy, reason) => runId && void run(() => closeRun(runId, closedBy, reason, api), setStatus),
    reset: () => {
      setStatus(null);
      setApiError(null);
      setPastError(null);
      setRunInUrl(null);
    },
  };

  return (
    <RunScreen
      mode="live"
      runId={runId}
      events={events}
      invalidEvents={errors}
      connection={connection}
      status={status}
      busy={busy}
      started={runId !== null || Boolean(initialRunId)}
      apiError={apiError}
      pastError={pastError}
      approvers={approvers}
      actions={actions}
      toolbar={toolbar}
    />
  );
}
