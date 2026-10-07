import { apiBase } from "@/lib/sources";

export type FetchFn = typeof fetch;

export interface RunStatus {
  run_id: string;
  state: "running" | "waiting" | "finished";
  status: string;
  pending: ({ type: "answer" | "approval" } & Record<string, unknown>) | null;
}

export interface Decision {
  decision: "approved" | "rejected";
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

async function post(path: string, body: unknown, o: ApiOptions): Promise<RunStatus> {
  const base = (o.baseUrl ?? apiBase()).replace(/\/$/, "");
  const f = o.fetchFn ?? fetch;
  let res: Response;
  try {
    res = await f(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
  return data as RunStatus;
}

export const startRun = (changeTime: string, o: ApiOptions = {}) => post("/runs", { change_time: changeTime }, o);

export const answerRun = (runId: string, answer: string, o: ApiOptions = {}) =>
  post(`/runs/${encodeURIComponent(runId)}/answer`, { answer }, o);

export const decideApproval = (runId: string, d: Decision, o: ApiOptions = {}) =>
  post(`/runs/${encodeURIComponent(runId)}/approval`, { reason: "", ...d }, o);
