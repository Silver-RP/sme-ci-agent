import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DecisionPanel } from "@/components/run/DecisionPanel";
import { MeasurementCard } from "@/components/run/MeasurementCard";
import { ProposalStage } from "@/components/run/ProposalStage";
import { RunScreen } from "@/components/run/RunScreen";
import { ActivityFeed, HypothesisBoard } from "@/components/run/SidePanels";
import { ErrorStage, QuestionStage, ThinkingStage } from "@/components/run/Stages";
import { friendlyError } from "@/lib/describe";
import { buildRunModel } from "@/lib/runModel";
import { chooseOption, eventsUntilStep, recording, stepStatus } from "./helpers";

const APPROVERS = ["alice", "bob"];

describe("measurement verdict reads one way (UX review item 4)", () => {
  it("a small move that misses the target is red and says how far it is", () => {
    const m = buildRunModel(eventsUntilStep("run-rollback", 1)).lastMeasurement!;
    render(<MeasurementCard m={m} compact />);
    expect(screen.getByTestId("measure-verdict")).toHaveTextContent("Chưa đạt");
    expect(screen.getByTestId("measure-summary")).toHaveTextContent(/còn xa mục tiêu 2,0%/);
    expect(screen.getByTestId("measure-summary")).toHaveClass("text-bad");
  });

  it("a passed measurement says the target was reached", () => {
    render(<MeasurementCard m={buildRunModel(recording("run-happy").events).lastMeasurement!} />);
    expect(screen.getByTestId("measure-summary")).toHaveTextContent("KPI đã về mục tiêu 2,0%.");
  });
});

describe("rollback in plain Vietnamese (items 1 and 4)", () => {
  it("builds the sentence from fields and names which content comes back", () => {
    const model = buildRunModel(eventsUntilStep("run-rollback", 1));
    render(
      <ProposalStage
        pending={stepStatus("run-rollback", 1).pending!}
        approvers={APPROVERS}
        busy={false}
        lastMeasurement={model.lastMeasurement}
        restoreVersion={22}
        onDecide={vi.fn()}
      />,
    );
    expect(screen.getByTestId("proposal-change")).toHaveTextContent("Đưa SOP-RFL-001 về nội dung của bản v22");
    expect(screen.getByTestId("sop-versions")).toHaveTextContent("Khôi phục nội dung v22 (lưu thành v24)");
    // the backend's English sentence is only in the folded technical details
    expect(screen.getByTestId("tech-detail")).toHaveTextContent("Roll back SOP SOP-RFL-001 to version 22");
  });
});

describe("approver is offered again, never sent by itself (item 3)", () => {
  it("pre-selects the replay approver; the decision still needs a click", () => {
    const onDecide = vi.fn();
    render(<DecisionPanel kind="proposal" proposalId="p1" approvers={APPROVERS} defaultApprover="bob" busy={false} onDecide={onDecide} />);
    expect(screen.getByLabelText("Người duyệt")).toHaveTextContent("bob");
    expect(onDecide).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("decide-approved"));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ decided_by: "bob", decision: "approved" }));
  });

  it("remembers the last chosen name for the next decision in this tab", () => {
    const { unmount } = render(<DecisionPanel kind="proposal" proposalId="p1" approvers={APPROVERS} busy={false} onDecide={vi.fn()} />);
    chooseOption("Người duyệt", "alice");
    unmount();
    render(<DecisionPanel kind="rollback" proposalId="r1" approvers={APPROVERS} busy={false} onDecide={vi.fn()} />);
    expect(screen.getByLabelText("Người duyệt")).toHaveTextContent("alice");
    expect(screen.getByTestId("decide-approved")).toBeEnabled();
  });
});

describe("acceptance criteria kept (FR-01.1, FR-04.2, FR-02) and the FR-05 change", () => {
  // FR-05 changed by decision of vai D (README "Quyết định đã chốt"): one confirm button, optional note
  it("too few points after the change: one confirm button, the backend sentence folded away", () => {
    const onAnswer = vi.fn();
    const model = buildRunModel(recording("run-insufficient-evidence").events);
    render(<QuestionStage pending={stepStatus("run-insufficient-evidence", 1).pending!} model={model} evidence busy={false} onAnswer={onAnswer} />);
    expect(screen.getByTestId("measure-insufficient")).toBeInTheDocument();
    expect(screen.queryByLabelText("Câu trả lời của bạn")).toBeNull();
    expect(screen.getByTestId("tech-detail")).toHaveTextContent("Not enough evidence yet");
    fireEvent.click(screen.getByTestId("answer-submit"));
    expect(onAnswer).toHaveBeenCalledWith("Đã chờ thêm dữ liệu, đo lại.");
  });

  it("an optional note replaces the default confirmation", () => {
    const onAnswer = vi.fn();
    const model = buildRunModel(recording("run-insufficient-evidence").events);
    render(<QuestionStage pending={stepStatus("run-insufficient-evidence", 1).pending!} model={model} evidence busy={false} onAnswer={onAnswer} />);
    fireEvent.click(screen.getByText(/Thêm ghi chú/));
    fireEvent.change(screen.getByLabelText("Câu trả lời của bạn"), { target: { value: "line restarted Monday" } });
    fireEvent.click(screen.getByTestId("answer-submit"));
    expect(onAnswer).toHaveBeenCalledWith("line restarted Monday");
  });

  it("FR-01.1: the action sentence shows the parameter code", () => {
    render(<ProposalStage pending={stepStatus("run-happy", 1).pending!} approvers={APPROVERS} busy={false} lastMeasurement={null} onDecide={vi.fn()} />);
    expect(screen.getByTestId("proposal-action")).toHaveTextContent(/Máy M02.*zone3_setpoint_c.*180/);
  });

  it("FR-04.2: the first line of the error stays on screen next to the plain words", () => {
    render(<ErrorStage message={"RuntimeError: 529 overloaded\nTraceback..."} retryable busy={false} onRetry={vi.fn()} />);
    expect(screen.getByTestId("run-error-raw")).toBeVisible();
    expect(screen.getByTestId("run-error-raw")).toHaveTextContent(/^RuntimeError: 529 overloaded$/);
  });

  it("FR-02 on narrow screens: the panels open by themselves while the agent investigates", () => {
    const actions = { answer: vi.fn(), decide: vi.fn(), retry: vi.fn() };
    render(
      <RunScreen
        mode="watch"
        runId="run_1"
        connection="open"
        busy={false}
        approvers={APPROVERS}
        actions={actions}
        events={recording("run-happy").events.slice(0, 2)}
        status={{ run_id: "run_1", state: "running", status: "", pending: null }}
        started
      />,
    );
    expect(screen.getByTestId("context-panels")).toBeInTheDocument();
  });
});

describe("thinking stage shows real steps (item 6)", () => {
  it("lists the tools already called and the step in progress", () => {
    render(<ThinkingStage model={buildRunModel(recording("run-happy").events)} />);
    const steps = screen.getByTestId("thinking-steps");
    expect(steps).toHaveTextContent("Quét KPI");
    expect(steps).toHaveTextContent("Tìm tương quan");
  });
});

describe("errors (item 8)", () => {
  it("names the kind of problem in plain words", () => {
    expect(friendlyError("RuntimeError: 529 overloaded")).toBe("Dịch vụ AI đang quá tải.");
    expect(friendlyError("ReadTimeout: timed out")).toBe("Dịch vụ AI phản hồi quá lâu.");
    expect(friendlyError("RateLimitError: 429")).toBe("Đã vượt giới hạn số lần gọi dịch vụ AI.");
    expect(friendlyError("KeyError: 'x'")).toBe("Một bước của agent gặp lỗi.");
  });

  it("a run that can no longer be retried can be closed with an approver and a reason", () => {
    const onClose = vi.fn();
    render(<ErrorStage message="RuntimeError: boom" retryable={false} busy={false} onRetry={vi.fn()} onClose={onClose} approvers={APPROVERS} />);
    const submit = screen.getByTestId("close-run-submit");
    expect(submit).toBeDisabled();
    chooseOption("Người duyệt", "alice");
    expect(submit).toBeDisabled(); // a reason is required too (H-48)
    fireEvent.change(screen.getByPlaceholderText("Lý do đóng (bắt buộc)"), { target: { value: "LLM quota used up" } });
    fireEvent.click(submit);
    expect(onClose).toHaveBeenCalledWith("alice", "LLM quota used up");
  });
});

describe("side panels stay short when shown side by side", () => {
  const tools = Array.from({ length: 12 }, (_, i) => ({ id: `t${i}`, ts: "2026-10-10T09:00:00", tool: "query_logs", args: { machine_id: "M02" }, ok: true, found: null }));
  const hypotheses = Array.from({ length: 5 }, (_, i) => ({ group: "machine", description: `cause ${i}`, confidence: 0.9 - i * 0.1 }));

  it("shows the newest tool calls and the strongest hypotheses, then how many more", () => {
    render(<ActivityFeed tools={tools} limit={3} />);
    expect(screen.getAllByTestId("tool-card")).toHaveLength(3);
    expect(screen.getByTestId("more-line")).toHaveTextContent("+9 bước trước đó");
  });

  it("hypotheses: top 2, the rest counted; without a limit everything is listed", () => {
    const { unmount } = render(<HypothesisBoard hypotheses={hypotheses} insufficient={false} limit={2} />);
    expect(screen.getAllByTestId("hypothesis")).toHaveLength(2);
    expect(screen.getByTestId("more-line")).toHaveTextContent("+3 giả thuyết");
    unmount();
    render(<HypothesisBoard hypotheses={hypotheses} insufficient={false} />);
    expect(screen.getAllByTestId("hypothesis")).toHaveLength(5);
    expect(screen.queryByTestId("more-line")).toBeNull();
  });
});

describe("run screen layout (items 2 and 10)", () => {
  it("before a run there are no empty side panels; afterwards the context strip and panels exist", () => {
    const actions = { start: vi.fn(), answer: vi.fn(), decide: vi.fn(), retry: vi.fn() };
    const common = { mode: "live" as const, runId: null, connection: "idle" as const, busy: false, approvers: APPROVERS, actions };
    const { unmount } = render(<RunScreen {...common} events={[]} status={null} started={false} />);
    expect(screen.queryByTestId("side-panels")).toBeNull();
    expect(screen.queryByTestId("context-strip")).toBeNull();
    unmount();
    render(<RunScreen {...common} events={eventsUntilStep("run-happy", 1)} status={stepStatus("run-happy", 1)} started />);
    expect(screen.getByTestId("context-strip")).toHaveTextContent("Tỷ lệ lỗi");
    expect(screen.getByTestId("side-panels")).toBeInTheDocument();
    // narrow screens: the panels open right under the strip, before the stage
    expect(screen.queryByTestId("context-panels")).toBeNull();
    fireEvent.click(screen.getByTestId("context-toggle"));
    const panels = screen.getByTestId("context-panels");
    expect(panels.compareDocumentPosition(screen.getByTestId("stage")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
