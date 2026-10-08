import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LiveRun } from "@/components/LiveRun";
import { RunControls } from "@/components/RunControls";
import { answerRun, ApiError, decideApproval, fetchApprovers, startRun, type RunStatus } from "@/lib/api";
import type { EventSourceLike } from "@/lib/sources";

const BASE = "http://api.test";

function resp(status: number, body: unknown): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}
const waitingAnswer: RunStatus = { run_id: "run_1", state: "waiting", status: "", pending: { type: "answer", question: "Any lot change?" } };
const PROPOSAL = {
  change: "Lower the setpoint on M02",
  rationale: "Setpoint drifted after the lot change",
  expected_kpi: { kpi: "defect_rate", direction: "decrease", target: 0.02 },
  sop_proposal: { sop_id: "SOP-1", new_content: "step 1\nstep 2 NEW" },
};
const waitingApproval: RunStatus = {
  run_id: "run_1",
  state: "waiting",
  status: "",
  pending: { type: "approval", kind: "proposal", proposal_id: "p1", proposal: PROPOSAL, current_sop: { sop_id: "SOP-1", version: 1, content: "step 1\nstep 2 OLD" } },
};
const waitingRollback: RunStatus = {
  run_id: "run_1",
  state: "waiting",
  status: "",
  pending: {
    type: "approval",
    kind: "rollback",
    proposal_id: "r1",
    proposal: { change: "Roll back SOP SOP-1 to version 1", rationale: "KPI after change is 0.09", sop_proposal: { sop_id: "SOP-1", new_content: "step 1\nstep 2 OLD" } },
    current_sop: { sop_id: "SOP-1", version: 2, content: "step 1\nstep 2 NEW" },
  },
};
const finished: RunStatus = { run_id: "run_1", state: "finished", status: "done", pending: null };

class FakeES implements EventSourceLike {
  static urls: string[] = [];
  readyState = 0;
  onopen = null;
  onerror = null;
  constructor(url: string) {
    FakeES.urls.push(url);
  }
  addEventListener() {}
  close() {}
}

describe("api calls", () => {
  it("send correct URL, method and body", async () => {
    const f = vi.fn().mockResolvedValue(resp(200, finished));
    await startRun("2026-01-15T00:00:00", { baseUrl: BASE + "/", fetchFn: f });
    await answerRun("run_1", "yes", { baseUrl: BASE, fetchFn: f });
    await decideApproval("run_1", { proposal_id: "p1", kind: "proposal", decision: "approved", decided_by: "qa" }, { baseUrl: BASE, fetchFn: f });
    const calls = f.mock.calls.map(([u, i]) => [u, i.method, JSON.parse(i.body)]);
    expect(calls).toEqual([
      [`${BASE}/runs`, "POST", { change_time: "2026-01-15T00:00:00" }],
      [`${BASE}/runs/run_1/answer`, "POST", { answer: "yes" }],
      [`${BASE}/runs/run_1/approval`, "POST", { reason: "", proposal_id: "p1", kind: "proposal", decision: "approved", decided_by: "qa" }],
    ]);
  });

  it("omits a blank change time and reads the approvers list", async () => {
    const f = vi.fn().mockResolvedValue(resp(200, finished));
    await startRun("  ", { baseUrl: BASE, fetchFn: f });
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({});
    const g = vi.fn().mockResolvedValue(resp(200, { approvers: ["alice", "bob"] }));
    expect(await fetchApprovers({ baseUrl: BASE, fetchFn: g })).toEqual(["alice", "bob"]);
    expect(await fetchApprovers({ fetchFn: vi.fn().mockRejectedValue(new Error("down")) })).toEqual([]);
    expect(await fetchApprovers({ fetchFn: vi.fn().mockResolvedValue(resp(500, {})) })).toEqual([]);
  });

  it.each([404, 409, 422])("surfaces %i with the backend detail", async (code) => {
    const f = vi.fn().mockResolvedValue(resp(code, { detail: code === 422 ? [{ msg: "bad field" }] : "nope" }));
    const err = await answerRun("r", "x", { baseUrl: BASE, fetchFn: f }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(code);
    expect(err.message).toBe(code === 422 ? "bad field" : "nope");
  });

  it("reports network failure and non-JSON error bodies", async () => {
    const down = vi.fn().mockRejectedValue(new Error("refused"));
    expect((await startRun("t", { fetchFn: down }).catch((e) => e)).message).toContain("refused");
    const bad = vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => { throw new Error("x"); } });
    expect((await startRun("t", { fetchFn: bad }).catch((e) => e)).message).toBe("HTTP 500");
  });
});

describe("RunControls visibility", () => {
  const mk = (status: RunStatus | null, runId: string | null) =>
    render(<RunControls runId={runId} status={status} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn: vi.fn() }} />);

  it("only start before a run", () => {
    mk(null, null);
    expect(screen.getByText("Start run")).toBeInTheDocument();
    expect(screen.queryByText("Send answer")).toBeNull();
    expect(screen.queryByText("Approve")).toBeNull();
  });
  it("only answer when asked", () => {
    mk(waitingAnswer, "run_1");
    expect(screen.getByTestId("pending-question")).toHaveTextContent("Any lot change?");
    expect(screen.queryByText("Start run")).toBeNull();
    expect(screen.queryByText("Approve")).toBeNull();
  });
  it("only approve/reject when waiting for approval", () => {
    mk(waitingApproval, "run_1");
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
    expect(screen.queryByText("Send answer")).toBeNull();
  });
  it("nothing when running or finished", () => {
    mk(finished, "run_1");
    expect(screen.queryByText("Approve")).toBeNull();
    expect(screen.queryByText("Send answer")).toBeNull();
    expect(screen.queryByText("Start run")).toBeNull();
  });
});

describe("live flow", () => {
  it("start -> answer -> approval, approval only after a click, repeated renders do not resend", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(resp(201, waitingAnswer))
      .mockResolvedValueOnce(resp(200, waitingApproval))
      .mockResolvedValueOnce(resp(200, finished));
    FakeES.urls = [];
    const { rerender } = render(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    fireEvent.change(screen.getByPlaceholderText(/2026/), { target: { value: "2026-01-15T00:00:00" } });
    fireEvent.click(screen.getByText("Start run"));
    await screen.findByText("Send answer");
    await waitFor(() => expect(FakeES.urls).toEqual([`${BASE}/runs/run_1/events?follow=true`]));

    fireEvent.change(screen.getByLabelText("Answer"), { target: { value: "yes, lot B" } });
    fireEvent.click(screen.getByText("Send answer"));
    await screen.findByText("Approve");
    rerender(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    await act(async () => {});
    expect(f).toHaveBeenCalledTimes(2); // no approval without a click

    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "qa_lead" } });
    fireEvent.click(screen.getByText("Reject"));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(3));
    const [url, init] = f.mock.calls[2];
    expect(url).toBe(`${BASE}/runs/run_1/approval`);
    expect(JSON.parse(init.body)).toEqual({ proposal_id: "p1", kind: "proposal", decision: "rejected", decided_by: "qa_lead", reason: "" });
    await waitFor(() => expect(screen.queryByText("Approve")).toBeNull());
  });

  it("shows API errors and keeps the buttons", async () => {
    const f = vi.fn().mockResolvedValue(resp(422, { detail: "bad reason" }));
    render(<RunControls runId="run_1" status={waitingApproval} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn: f }} />);
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
    fireEvent.click(screen.getByText("Approve"));
    expect(await screen.findByTestId("api-error")).toHaveTextContent("422: bad reason");
    expect(screen.getByText("Approve")).toBeInTheDocument();
  });
});

describe("approver field", () => {
  it("disables Approve/Reject while the approver is empty or blank, enables once filled", () => {
    const f = vi.fn();
    render(<RunControls runId="run_1" status={waitingApproval} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn: f }} />);
    expect(screen.getByText("Approve")).toBeDisabled();
    expect(screen.getByText("Reject")).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "   " } });
    expect(screen.getByText("Approve")).toBeDisabled();
    fireEvent.click(screen.getByText("Approve"));
    expect(f).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
    expect(screen.getByText("Approve")).toBeEnabled();
    expect(screen.getByText("Reject")).toBeEnabled();
  });

  it("shows the 422 message for an invalid approver and keeps the buttons", async () => {
    const f = vi.fn().mockResolvedValue(resp(422, { detail: "decided_by 'llm' is not a valid approver; allowed: alice" }));
    render(<RunControls runId="run_1" status={waitingApproval} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn: f }} />);
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "llm" } });
    fireEvent.click(screen.getByText("Approve"));
    expect(await screen.findByTestId("api-error")).toHaveTextContent("422: decided_by 'llm' is not a valid approver");
    expect(screen.getByText("Approve")).toBeEnabled();
  });

  it("offers names from the approvers list", () => {
    const { container } = render(
      <RunControls runId="run_1" status={waitingApproval} onStarted={vi.fn()} onStatus={vi.fn()} approvers={["alice", "bob"]} api={{ baseUrl: BASE, fetchFn: vi.fn() }} />,
    );
    expect([...container.querySelectorAll("datalist option")].map((o) => o.getAttribute("value"))).toEqual(["alice", "bob"]);
  });
});

describe("approval screen (R8/dev-04)", () => {
  const mk = (status: RunStatus, extra: { approvers?: string[]; fetchFn?: unknown; onStatus?: unknown } = {}) =>
    render(
      <RunControls
        runId="run_1"
        status={status}
        onStarted={vi.fn()}
        onStatus={(extra.onStatus as (s: RunStatus) => void) ?? vi.fn()}
        approvers={extra.approvers}
        api={{ baseUrl: BASE, fetchFn: (extra.fetchFn as typeof fetch) ?? vi.fn() }}
      />,
    );

  it("shows the proposal content next to the buttons: change, rationale, expected KPI, old and new SOP", () => {
    mk(waitingApproval);
    expect(screen.getByTestId("approval-title")).toHaveTextContent("Review proposal");
    expect(screen.getByTestId("proposal-change")).toHaveTextContent("Lower the setpoint on M02");
    expect(screen.getByTestId("proposal-rationale")).toHaveTextContent("Setpoint drifted");
    expect(screen.getByTestId("proposal-kpi")).toHaveTextContent("defect_rate decrease target 0.02");
    expect(screen.getByTestId("sop-old").textContent).toContain("step 2 OLD");
    expect(screen.getByTestId("sop-new").textContent).toContain("step 2 NEW");
    expect(screen.queryByTestId("rollback-explain")).toBeNull();
  });

  it("shows a proposal without a SOP change and without optional fields", () => {
    mk({ ...waitingApproval, pending: { type: "approval", kind: "proposal", proposal_id: "p2", proposal: { change: "Only a note" } } });
    expect(screen.getByTestId("proposal-change")).toHaveTextContent("Only a note");
    expect(screen.queryByTestId("sop-diff")).toBeNull();
    expect(screen.queryByTestId("proposal-kpi")).toBeNull();
  });

  it("rollback has its own title, explanation and button labels", () => {
    mk(waitingRollback);
    expect(screen.getByTestId("approval-title")).toHaveTextContent("Confirm rollback");
    expect(screen.getByTestId("rollback-explain")).toHaveTextContent("Rejecting keeps the applied SOP in force");
    expect(screen.getByTestId("sop-old").textContent).toContain("step 2 NEW");
    expect(screen.getByText("Approve rollback")).toBeInTheDocument();
    expect(screen.getByText("Reject rollback")).toBeInTheDocument();
  });

  it("sends proposal_id and kind of what is shown", async () => {
    const f = vi.fn().mockResolvedValue(resp(200, finished));
    mk(waitingRollback, { fetchFn: f });
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
    fireEvent.click(screen.getByText("Approve rollback"));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
    expect(JSON.parse(f.mock.calls[0][1].body)).toMatchObject({ proposal_id: "r1", kind: "rollback", decision: "approved" });
  });

  it("locks the buttons for an empty name and for a name outside the approvers list", () => {
    const f = vi.fn();
    mk(waitingApproval, { approvers: ["alice", "bob"], fetchFn: f });
    expect(screen.getByText("Approve")).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "mallory" } });
    expect(screen.getByText("Approve")).toBeDisabled();
    expect(screen.getByText("Reject")).toBeDisabled();
    expect(screen.getByTestId("approver-hint")).toHaveTextContent("mallory");
    fireEvent.click(screen.getByText("Approve"));
    expect(f).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: " Alice " } });
    expect(screen.getByText("Approve")).toBeEnabled();
    expect(screen.queryByTestId("approver-hint")).toBeNull();
  });

  it("locks the buttons when the pending approval has no proposal_id", () => {
    mk({ ...waitingApproval, pending: { type: "approval", kind: "proposal", proposal: PROPOSAL } });
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
    expect(screen.getByText("Approve")).toBeDisabled();
  });

  it("on 409 shows the message and refetches the run, handing the new status over", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(resp(409, { detail: "now waiting for rollback" }))
      .mockResolvedValueOnce(resp(200, waitingRollback));
    const onStatus = vi.fn();
    mk(waitingApproval, { fetchFn: f, onStatus });
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
    fireEvent.click(screen.getByText("Approve"));
    await waitFor(() => expect(onStatus).toHaveBeenCalledWith(waitingRollback));
    expect(f.mock.calls[1][0]).toBe(`${BASE}/runs/run_1`);
    expect(f.mock.calls[1][1].method).toBe("GET");
    expect(screen.getByTestId("api-error")).toHaveTextContent("409: now waiting for rollback");
  });

  it("422 does not refetch", async () => {
    const f = vi.fn().mockResolvedValue(resp(422, { detail: "bad" }));
    mk(waitingApproval, { fetchFn: f });
    fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
    fireEvent.click(screen.getByText("Approve"));
    await screen.findByTestId("api-error");
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("an error run shows the error and a Retry button that calls /retry", async () => {
    const f = vi.fn().mockResolvedValue(resp(200, waitingApproval));
    const onStatus = vi.fn();
    mk({ run_id: "run_1", state: "error", status: "error", pending: null, error: "RateLimitError: 429" }, { fetchFn: f, onStatus });
    expect(screen.getByTestId("run-error")).toHaveTextContent("RateLimitError: 429");
    expect(screen.queryByText("Approve")).toBeNull();
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => expect(onStatus).toHaveBeenCalledWith(waitingApproval));
    expect(f.mock.calls[0][0]).toBe(`${BASE}/runs/run_1/retry`);
    expect(f.mock.calls[0][1].method).toBe("POST");
  });

  it("an answer question after insufficient evidence still shows the answer box", () => {
    mk({ run_id: "run_1", state: "waiting", status: "", pending: { type: "answer", question: "Not enough evidence yet: only 0 point(s)" } });
    expect(screen.getByTestId("pending-question")).toHaveTextContent("Not enough evidence yet");
    expect(screen.getByText("Send answer")).toBeInTheDocument();
  });
});
