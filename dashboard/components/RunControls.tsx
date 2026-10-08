"use client";

import { useState } from "react";
import { answerRun, ApiError, decideApproval, startRun, type ApiOptions, type RunStatus } from "@/lib/api";

/**
 * Start / answer / approval controls. Buttons appear only for the state the backend reports
 * (`pending`). Approval is sent only on an explicit click by a person; nothing is automatic.
 */
export function RunControls({
  runId,
  status,
  onStarted,
  onStatus,
  api,
  approvers,
}: {
  runId: string | null;
  status: RunStatus | null;
  onStarted: (s: RunStatus) => void;
  onStatus: (s: RunStatus) => void;
  api?: ApiOptions;
  approvers?: string[];
}) {
  const [changeTime, setChangeTime] = useState("");
  const [answer, setAnswer] = useState("");
  const [decidedBy, setDecidedBy] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<RunStatus>, done: (s: RunStatus) => void) {
    setBusy(true);
    setError(null);
    try {
      done(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status || "error"}: ${e.message}` : String(e));
    } finally {
      setBusy(false);
    }
  }

  const pending = status?.pending ?? null;
  return (
    <section aria-label="Run controls">
      {!runId && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => startRun(changeTime.trim(), api), onStarted);
          }}
        >
          <label>
            Change time (ISO){" "}
            <input value={changeTime} onChange={(e) => setChangeTime(e.target.value)} placeholder="2026-01-15T00:00:00" />
          </label>{" "}
          <button type="submit" disabled={busy}>
            Start run
          </button>
        </form>
      )}
      {runId && pending?.type === "answer" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => answerRun(runId, answer, api), (s) => {
              setAnswer("");
              onStatus(s);
            });
          }}
        >
          <p data-testid="pending-question">{String(pending.question ?? "The agent needs more information.")}</p>
          <input aria-label="Answer" value={answer} onChange={(e) => setAnswer(e.target.value)} />{" "}
          <button type="submit" disabled={busy}>
            Send answer
          </button>
        </form>
      )}
      {runId && pending?.type === "approval" && (
        <div data-testid="pending-approval">
          <p>Waiting for your decision{pending.kind ? ` (${String(pending.kind)})` : ""}.</p>
          <label>
            Decided by{" "}
            <input list="approvers-list" value={decidedBy} onChange={(e) => setDecidedBy(e.target.value)} />
            <datalist id="approvers-list">
              {(approvers ?? []).map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
          </label>{" "}
          <label>
            Reason <input value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>{" "}
          {(["approved", "rejected"] as const).map((d) => (
            <button
              key={d}
              type="button"
              disabled={busy || decidedBy.trim() === ""}
              onClick={() =>
                void run(() => decideApproval(runId, { decision: d, decided_by: decidedBy.trim(), reason }, api), onStatus)
              }
            >
              {d === "approved" ? "Approve" : "Reject"}
            </button>
          ))}
        </div>
      )}
      {status && <p className="muted" data-testid="run-state">State: {status.state}</p>}
      {error && (
        <p role="alert" data-testid="api-error">
          {error}
        </p>
      )}
    </section>
  );
}
