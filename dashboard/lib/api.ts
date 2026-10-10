import { apiBase } from "@/lib/sources";

export type FetchFn = typeof fetch;

export interface RunStatus {
  run_id: string;
  state: "running" | "waiting" | "finished" | "error";
  status: string;
  pending: ({ type: "answer" | "approval" } & Record<string, unknown>) | null;
  /** set when state is "error" (the step failed; POST /runs/{id}/retry runs it again) */
  error?: string;
  /** with state "error": false once /retry was used up (loop.max_retries); then the UI hides Retry */
  retryable?: boolean;
}

export interface Decision {
  /** what the person was shown: the backend answers 409 when it no longer matches the pending approval */
  proposal_id: string;
  kind: "proposal" | "rollback" | "halt";
  /** proposal: approved | rejected | revise (dispute the hypothesis / add information, needs a reason);
   *  rollback: approved | rejected; halt (run stopped at a limit): investigate | finish */
  decision: "approved" | "rejected" | "revise" | "investigate" | "finish";
  decided_by: string;
  reason?: string;
}

/** HTTP error from the backend (404 run missing, 409 wrong state, 422 invalid body). */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export interface ApiOptions {
  baseUrl?: string;
  fetchFn?: FetchFn;
}

function detailText(d: unknown): string {
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x && typeof x === "object" && "msg" in x ? String((x as { msg: unknown }).msg) : JSON.stringify(x))).join("; ");
  return d === undefined ? "" : JSON.stringify(d);
}

async function call<T = RunStatus>(method: "GET" | "POST", path: string, body: unknown, o: ApiOptions): Promise<T> {
  const base = (o.baseUrl ?? apiBase()).replace(/\/$/, "");
  const f = o.fetchFn ?? fetch;
  let res: Response;
  try {
    res = await f(`${base}${path}`, {
      method,
      ...(method === "POST" ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
    });
  } catch (e) {
    throw new ApiError(0, `Network error: ${e instanceof Error ? e.message : String(e)}`);
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    const d = data && typeof data === "object" && "detail" in data ? detailText((data as { detail: unknown }).detail) : "";
    throw new ApiError(res.status, d || `HTTP ${res.status}`);
  }
  return data as T;
}

const post = (path: string, body: unknown, o: ApiOptions) => call("POST", path, body, o);

/** Read-only GET with the same error handling as the run actions (used by lib/readApi.ts). */
export const getJson = <T>(path: string, o: ApiOptions = {}) => call<T>("GET", path, null, o);

/** Current status of a run (used to refresh after a 409). */
export const getRun = (runId: string, o: ApiOptions = {}) => call("GET", `/runs/${encodeURIComponent(runId)}`, null, o);

/** Close a run in error that can no longer be retried (H-48); both fields are required by the backend. */
export const closeRun = (runId: string, closedBy: string, reason: string, o: ApiOptions = {}) =>
  post(`/runs/${encodeURIComponent(runId)}/close`, { closed_by: closedBy, reason }, o);

/** Run the failed step again (only when the run is in state "error"). */
export const retryRun = (runId: string, o: ApiOptions = {}) => post(`/runs/${encodeURIComponent(runId)}/retry`, {}, o);

/** A blank change time is omitted: the backend then uses the end of the anomaly Detect finds. */
export const startRun = (changeTime: string, o: ApiOptions = {}) =>
  post("/runs", changeTime.trim() === "" ? {} : { change_time: changeTime }, o);

/** Names allowed to approve or reject (GET /config/approvers). Returns [] if the call fails. */
export async function fetchApprovers(o: ApiOptions = {}): Promise<string[]> {
  const base = (o.baseUrl ?? apiBase()).replace(/\/$/, "");
  try {
    const res = await (o.fetchFn ?? fetch)(`${base}/config/approvers`);
    if (!res.ok) return [];
    const data = (await res.json()) as { approvers?: unknown };
    return Array.isArray(data.approvers) ? data.approvers.map(String) : [];
  } catch {
    return [];
  }
}

export const answerRun = (runId: string, answer: string, o: ApiOptions = {}) =>
  post(`/runs/${encodeURIComponent(runId)}/answer`, { answer }, o);

export const decideApproval = (runId: string, d: Decision, o: ApiOptions = {}) =>
  post(`/runs/${encodeURIComponent(runId)}/approval`, { reason: "", ...d }, o);
