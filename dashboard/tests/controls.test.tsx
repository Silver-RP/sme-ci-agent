import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LiveRun } from "@/components/LiveRun";
import { RunControls } from "@/components/RunControls";
import { answerRun, ApiError, decideApproval, startRun, type RunStatus } from "@/lib/api";
import type { EventSourceLike } from "@/lib/sources";

const BASE = "http://api.test";

function resp(status: number, body: unknown): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}
const waitingAnswer: RunStatus = { run_id: "run_1", state: "waiting", status: "", pending: { type: "answer", question: "Any lot change?" } };
const waitingApproval: RunStatus = { run_id: "run_1", state: "waiting", status: "", pending: { type: "approval", kind: "proposal" } };
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
    await decideApproval("run_1", { decision: "approved", decided_by: "qa" }, { baseUrl: BASE, fetchFn: f });
    const calls = f.mock.calls.map(([u, i]) => [u, i.method, JSON.parse(i.body)]);
    expect(calls).toEqual([
      [`${BASE}/runs`, "POST", { change_time: "2026-01-15T00:00:00" }],
      [`${BASE}/runs/run_1/answer`, "POST", { answer: "yes" }],
      [`${BASE}/runs/run_1/approval`, "POST", { reason: "", decision: "approved", decided_by: "qa" }],
    ]);
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
    expect(JSON.parse(init.body)).toEqual({ decision: "rejected", decided_by: "qa_lead", reason: "" });
    await waitFor(() => expect(screen.queryByText("Approve")).toBeNull());
  });

  it("shows API errors and keeps the buttons", async () => {
    const f = vi.fn().mockResolvedValue(resp(409, { detail: "not waiting" }));
    render(<RunControls runId="run_1" status={waitingApproval} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn: f }} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(await screen.findByTestId("api-error")).toHaveTextContent("409: not waiting");
    expect(screen.getByText("Approve")).toBeInTheDocument();
  });
});
