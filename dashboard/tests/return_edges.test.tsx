import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunControls } from "@/components/RunControls";
import type { RunStatus } from "@/lib/api";

const BASE = "http://api.test";
const resp = (status: number, body: unknown) => ({ ok: status < 300, status, json: async () => body }) as Response;
const finished: RunStatus = { run_id: "run_1", state: "finished", status: "closed", pending: null };

const proposal: RunStatus = {
  run_id: "run_1",
  state: "waiting",
  status: "",
  pending: { type: "approval", kind: "proposal", proposal_id: "p1", proposal: { change: "Lower the setpoint" } },
};
const halt: RunStatus = {
  run_id: "run_1",
  state: "waiting",
  status: "awaiting_human",
  pending: {
    type: "approval",
    kind: "halt",
    proposal_id: "halt_1",
    reason: "max_rollbacks_reached",
    options: ["investigate", "finish"],
    sop_still_in_force: true,
    sop_id: "SOP-1",
    sop_version: 2,
  },
};

function mk(status: RunStatus, fetchFn = vi.fn()) {
  render(<RunControls runId="run_1" status={status} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn }} />);
  fireEvent.change(screen.getByLabelText(/Decided by/), { target: { value: "alice" } });
  return fetchFn;
}

describe("return edges on the proposal", () => {
  it("offers approve, reject and dispute; dispute needs a reason", () => {
    mk(proposal);
    expect(screen.getByText("Approve")).toBeEnabled();
    expect(screen.getByText("Reject")).toBeEnabled();
    expect(screen.getByText("Dispute / add information")).toBeDisabled();
    expect(screen.getByTestId("revise-hint")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "  " } });
    expect(screen.getByText("Dispute / add information")).toBeDisabled(); // blank is not feedback
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "M02 was serviced" } });
    expect(screen.getByText("Dispute / add information")).toBeEnabled();
    expect(screen.queryByTestId("revise-hint")).toBeNull();
  });

  it("sends revise with proposal_id, kind and the feedback", async () => {
    const f = mk(proposal, vi.fn().mockResolvedValue(resp(200, proposal)));
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "M02 was serviced" } });
    fireEvent.click(screen.getByText("Dispute / add information"));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({
      proposal_id: "p1",
      kind: "proposal",
      decision: "revise",
      decided_by: "alice",
      reason: "M02 was serviced",
    });
  });

  it("a rollback prompt has no dispute button", () => {
    mk({ ...proposal, pending: { ...proposal.pending!, kind: "rollback" } });
    expect(screen.queryByText("Dispute / add information")).toBeNull();
    expect(screen.getByText("Approve rollback")).toBeInTheDocument();
  });
});

describe("resumable halt", () => {
  it("shows why the run stopped, that the SOP stays in force, and the two choices", () => {
    mk(halt);
    expect(screen.getByTestId("approval-title")).toHaveTextContent("Run stopped");
    expect(screen.getByTestId("halt-reason")).toHaveTextContent("max_rollbacks_reached");
    expect(screen.getByTestId("sop-in-force")).toHaveTextContent("SOP-1 v2");
    expect(screen.getByText("Investigate again")).toBeEnabled();
    expect(screen.getByText("Finish run")).toBeEnabled();
    expect(screen.queryByText("Approve")).toBeNull();
  });

  it("does not claim an SOP is in force when the backend does not say so", () => {
    mk({ ...halt, pending: { ...halt.pending!, sop_still_in_force: false } });
    expect(screen.queryByTestId("sop-in-force")).toBeNull();
  });

  it.each([
    ["Investigate again", "investigate"],
    ["Finish run", "finish"],
  ])("%s sends the halt id and kind", async (label, decision) => {
    const f = mk(halt, vi.fn().mockResolvedValue(resp(200, finished)));
    fireEvent.click(screen.getByText(label));
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
    expect(f.mock.calls[0][0]).toBe(`${BASE}/runs/run_1/approval`);
    expect(JSON.parse(f.mock.calls[0][1].body)).toMatchObject({ proposal_id: "halt_1", kind: "halt", decision, decided_by: "alice" });
  });

  it("is locked until an approver name is given", () => {
    render(<RunControls runId="run_1" status={halt} onStarted={vi.fn()} onStatus={vi.fn()} api={{ baseUrl: BASE, fetchFn: vi.fn() }} />);
    expect(screen.getByText("Investigate again")).toBeDisabled();
    expect(screen.getByText("Finish run")).toBeDisabled();
  });
});
