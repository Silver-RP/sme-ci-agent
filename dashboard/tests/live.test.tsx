import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveRun } from "@/components/LiveRun";
import { ReplayRun } from "@/components/ReplayRun";
import { answerRun, ApiError, decideApproval, fetchApprovers, startRun, type RunStatus } from "@/lib/api";
import type { EventSourceLike } from "@/lib/sources";
import { chooseOption, resp, stepStatus } from "./helpers";

/** The approver field is a free text box until GET /config/approvers answers, then a select (a button). */
const approverListLoaded = () => waitFor(() => expect(screen.getByLabelText("Người duyệt").tagName).toBe("BUTTON"));

const BASE = "http://api.test";
const finished: RunStatus = { run_id: "run_1", state: "finished", status: "completed", pending: null };
const waitingAnswer: RunStatus = { ...stepStatus("run-happy", 0), run_id: "run_1" };
const waitingApproval: RunStatus = { ...stepStatus("run-happy", 1), run_id: "run_1" };
const errored: RunStatus = { run_id: "run_1", state: "error", status: "error", pending: null, error: "RuntimeError: 529 overloaded", retryable: true };

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

beforeEach(() => {
  FakeES.urls = [];
  // approvers lookup uses the global fetch
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(resp(200, { approvers: ["alice", "bob"] })));
});
afterEach(() => vi.unstubAllGlobals());

describe("api calls", () => {
  it("send correct URL, method and body", async () => {
    const f = vi.fn().mockResolvedValue(resp(200, finished));
    await startRun("2026-01-15T00:00:00", { baseUrl: BASE + "/", fetchFn: f });
    await answerRun("run_1", "yes", { baseUrl: BASE, fetchFn: f });
    await decideApproval("run_1", { proposal_id: "p1", kind: "proposal", decision: "approved", decided_by: "qa" }, { baseUrl: BASE, fetchFn: f });
    expect(f.mock.calls.map(([u, i]) => [u, i.method, JSON.parse(i.body)])).toEqual([
      [`${BASE}/runs`, "POST", { change_time: "2026-01-15T00:00:00" }],
      [`${BASE}/runs/run_1/answer`, "POST", { answer: "yes" }],
      [`${BASE}/runs/run_1/approval`, "POST", { reason: "", proposal_id: "p1", kind: "proposal", decision: "approved", decided_by: "qa" }],
    ]);
  });

  it("omits a blank change time and reads the approvers list", async () => {
    const f = vi.fn().mockResolvedValue(resp(200, finished));
    await startRun("  ", { baseUrl: BASE, fetchFn: f });
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({});
    expect(await fetchApprovers({ baseUrl: BASE, fetchFn: vi.fn().mockResolvedValue(resp(200, { approvers: ["alice"] })) })).toEqual(["alice"]);
    expect(await fetchApprovers({ fetchFn: vi.fn().mockRejectedValue(new Error("down")) })).toEqual([]);
  });

  it.each([404, 409, 422])("surfaces %i with the backend detail", async (code) => {
    const f = vi.fn().mockResolvedValue(resp(code, { detail: code === 422 ? [{ msg: "bad field" }] : "nope" }));
    const err = await answerRun("r", "x", { baseUrl: BASE, fetchFn: f }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe(code === 422 ? "bad field" : "nope");
  });
});

describe("live run", () => {
  it("start -> answer -> approval; decisions only on a click, with proposal_id and kind", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(resp(201, waitingAnswer))
      .mockResolvedValueOnce(resp(200, waitingApproval))
      .mockResolvedValueOnce(resp(200, finished));
    const { rerender } = render(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    fireEvent.click(screen.getByTestId("start-button"));
    await screen.findByTestId("question-stage");
    await waitFor(() => expect(FakeES.urls).toEqual([`${BASE}/runs/run_1/events?follow=true`]));
    expect(screen.getByTestId("run-status")).toHaveAttribute("data-phase", "answer");

    fireEvent.change(screen.getByLabelText("Câu trả lời của bạn"), { target: { value: "yes, lot B" } });
    fireEvent.click(screen.getByTestId("answer-submit"));
    await screen.findByTestId("decision-panel");
    rerender(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    await act(async () => {});
    expect(f).toHaveBeenCalledTimes(2); // nothing sent without a click

    await approverListLoaded();
    chooseOption("Người duyệt", "alice");
    fireEvent.click(screen.getByTestId("decide-approved"));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(3));
    const [url, init] = f.mock.calls[2];
    expect(url).toBe(`${BASE}/runs/run_1/approval`);
    expect(JSON.parse(init.body)).toEqual({ proposal_id: waitingApproval.pending!.proposal_id, kind: "proposal", decision: "approved", decided_by: "alice", reason: "" });
    await screen.findByTestId("outcome-stage");
  });

  it("revise (dispute / add information) sends proposal_id, kind and the reason, only after a reason is typed", async () => {
    const f = vi.fn().mockResolvedValueOnce(resp(201, waitingApproval)).mockResolvedValueOnce(resp(200, waitingAnswer));
    render(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    fireEvent.click(screen.getByTestId("start-button"));
    await screen.findByTestId("decision-panel");
    await approverListLoaded();
    chooseOption("Người duyệt", "alice");
    expect(screen.getByTestId("decide-revise")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Lý do / thông tin bổ sung"), { target: { value: "M02 was serviced that night" } });
    fireEvent.click(screen.getByTestId("decide-revise"));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2));
    expect(JSON.parse(f.mock.calls[1][1].body)).toEqual({
      proposal_id: waitingApproval.pending!.proposal_id,
      kind: "proposal",
      decision: "revise",
      decided_by: "alice",
      reason: "M02 was serviced that night",
    });
  });

  it("on 409 shows the message and reloads the run", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(resp(201, waitingApproval))
      .mockResolvedValueOnce(resp(409, { detail: "now waiting for rollback" }))
      .mockResolvedValueOnce(resp(200, { ...stepStatus("run-rollback", 1), run_id: "run_1" }));
    render(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    fireEvent.click(screen.getByTestId("start-button"));
    await screen.findByTestId("decision-panel");
    await approverListLoaded();
    chooseOption("Người duyệt", "alice");
    fireEvent.click(screen.getByTestId("decide-approved"));
    expect(await screen.findByTestId("api-error")).toHaveTextContent("409: now waiting for rollback");
    expect(f.mock.calls[2][0]).toBe(`${BASE}/runs/run_1`);
    await waitFor(() => expect(screen.getByTestId("approval-title")).toHaveTextContent("KPI không đạt"));
  });

  it("error -> Retry calls /retry and reopens the event stream (H-13)", async () => {
    const f = vi.fn().mockResolvedValueOnce(resp(201, errored)).mockResolvedValueOnce(resp(200, waitingApproval));
    render(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    fireEvent.click(screen.getByTestId("start-button"));
    expect(await screen.findByTestId("run-error-message")).toHaveTextContent("Dịch vụ AI đang quá tải.");
    expect(screen.getByTestId("run-error-raw")).toHaveTextContent("RuntimeError: 529 overloaded");
    await waitFor(() => expect(FakeES.urls).toHaveLength(1));
    fireEvent.click(screen.getByTestId("retry-button"));
    await screen.findByTestId("decision-panel");
    expect(f.mock.calls[1][0]).toBe(`${BASE}/runs/run_1/retry`);
    await waitFor(() => expect(FakeES.urls).toHaveLength(2));
    expect(screen.getByTestId("past-error")).toHaveTextContent("RuntimeError: 529 overloaded");
  });

  it("hides Retry when the backend says it is not retryable", async () => {
    const f = vi.fn().mockResolvedValueOnce(resp(201, { ...errored, retryable: false }));
    render(<LiveRun api={{ baseUrl: BASE, fetchFn: f }} ctor={FakeES} />);
    fireEvent.click(screen.getByTestId("start-button"));
    await screen.findByTestId("not-retryable");
    expect(screen.queryByTestId("retry-button")).toBeNull();
  });
});

/** Step fake timers in small slices so React runs the effect that schedules the next replay tick. */
function tick(ms: number) {
  for (let t = 0; t < ms; t += 20) act(() => vi.advanceTimersByTime(20));
}

describe("replay (FR-07)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("plays the happy recording and waits for the presenter at the question and the approval", () => {
    render(<ReplayRun file="run-happy" intervalMs={10} />);
    expect(screen.getByTestId("replay-banner")).toBeInTheDocument();
    tick(1000);
    expect(screen.getByTestId("question-stage")).toBeInTheDocument();
    expect(screen.getByTestId("replay-hint")).toHaveTextContent("Bản ghi trả lời");

    fireEvent.change(screen.getByLabelText("Câu trả lời của bạn"), { target: { value: "ok" } });
    fireEvent.click(screen.getByTestId("answer-submit"));
    tick(1000);
    expect(screen.getByTestId("proposal-card")).toHaveAttribute("data-kind", "proposal");

    chooseOption("Người duyệt", "alice");
    fireEvent.click(screen.getByTestId("decide-approved"));
    tick(1000);
    expect(screen.getByTestId("outcome-stage")).toHaveAttribute("data-phase", "completed");
    expect(screen.getByTestId("kaizen-card")).toBeInTheDocument();
    expect(screen.getByTestId("loop-stepper").querySelector('[data-step="learn"]')).toHaveAttribute("data-state", "done");
  });

  it("error recording: error screen, Retry continues, the past error stays visible", () => {
    render(<ReplayRun file="run-error-retry" intervalMs={10} />);
    tick(1000);
    expect(screen.getByTestId("run-error-raw")).toHaveTextContent("529 overloaded");
    fireEvent.click(screen.getByTestId("retry-button"));
    tick(2000);
    expect(screen.getByTestId("proposal-card")).toBeInTheDocument();
    expect(screen.getByTestId("past-error")).toBeInTheDocument();
  });

  it("Auto mode walks a whole recording without clicks", () => {
    render(<ReplayRun file="run-rollback" intervalMs={10} />);
    fireEvent.click(screen.getByTestId("replay-auto"));
    tick(60_000);
    expect(screen.getByTestId("outcome-stage")).toHaveAttribute("data-phase", "completed");
    expect(screen.getByTestId("loop-stepper").querySelector('[data-step="rollback"]')).not.toBeNull();
  });
});
