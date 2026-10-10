import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DecisionPanel } from "@/components/run/DecisionPanel";
import { MeasurementCard } from "@/components/run/MeasurementCard";
import { ProposalStage } from "@/components/run/ProposalStage";
import { ErrorStage, HaltStage, OutcomeStage, QuestionStage } from "@/components/run/Stages";
import { buildRunModel } from "@/lib/runModel";
import { eventsUntilStep, recording, stepStatus } from "./helpers";

const APPROVERS = ["alice", "bob", "qa_lead"];
const happyPending = stepStatus("run-happy", 1).pending!;

function choose(name: string) {
  fireEvent.change(screen.getByLabelText("Người duyệt"), { target: { value: name } });
}

describe("ProposalStage (S5, FR-01) with the real R9i payload", () => {
  it("shows the five blocks: why, what, SOP old -> new, expected KPI, decision", () => {
    render(<ProposalStage pending={happyPending} approvers={APPROVERS} busy={false} lastMeasurement={null} onDecide={vi.fn()} />);
    expect(screen.getByTestId("approval-title")).toHaveTextContent("Agent đề xuất thay đổi, cần bạn duyệt");
    // why
    expect(screen.getByTestId("proposal-group")).toHaveTextContent("Máy móc");
    expect(screen.getByTestId("proposal-hypothesis")).toHaveTextContent("Setpoint bị đổi sai so với SOP");
    expect(within(screen.getByTestId("block-why")).getByRole("meter")).toHaveAttribute("aria-valuenow", "0.8");
    expect(screen.getByTestId("proposal-rationale")).toHaveTextContent("Evidence 0");
    // what: machine, parameter, value
    const action = screen.getByTestId("proposal-action");
    expect(action).toHaveTextContent("Máy M02");
    expect(action).toHaveTextContent("Nhiệt độ vùng 3");
    expect(action).toHaveTextContent("180");
    expect(action).toHaveTextContent("°C");
    expect(screen.getByTestId("proposal-change")).toHaveTextContent("Restore the setpoint");
    // SOP: same content in the scripted run -> "không đổi", versions v21 -> v22
    expect(screen.getByTestId("sop-unchanged")).toHaveTextContent("Nội dung SOP không đổi");
    expect(screen.getByTestId("sop-versions")).toHaveTextContent("v21");
    expect(screen.getByTestId("sop-versions")).toHaveTextContent("v22");
    // expected KPI
    expect(screen.getByTestId("proposal-kpi")).toHaveTextContent("Tỷ lệ lỗi giảm về 2,0%");
    expect(screen.getByTestId("decision-panel")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/null|undefined|NaN/);
  });

  it("colors added and removed SOP lines when the content changes", () => {
    const pending = { ...happyPending, current_sop: { sop_id: "SOP-RFL-001", version: 21, content: "Verify the setpoint.\nOld step." } };
    render(<ProposalStage pending={pending} approvers={APPROVERS} busy={false} lastMeasurement={null} onDecide={vi.fn()} />);
    const lines = within(screen.getByTestId("sop-lines")).getAllByRole("listitem");
    expect(lines.map((l) => l.getAttribute("data-kind"))).toEqual(["same", "del", "add"]);
    expect(screen.queryByTestId("sop-unchanged")).toBeNull();
  });

  it("rollback: own title, explanation, the failed measurement and rollback buttons", () => {
    const model = buildRunModel(eventsUntilStep("run-rollback", 1));
    render(
      <ProposalStage pending={stepStatus("run-rollback", 1).pending!} approvers={APPROVERS} busy={false} lastMeasurement={model.lastMeasurement} onDecide={vi.fn()} />,
    );
    expect(screen.getByTestId("approval-title")).toHaveTextContent("KPI không đạt, đề xuất quay về SOP trước");
    expect(screen.getByTestId("rollback-explain")).toBeInTheDocument();
    expect(screen.getByTestId("measure-verdict")).toHaveTextContent("Chưa đạt");
    expect(screen.getByText("Xác nhận rollback")).toBeInTheDocument();
    expect(screen.getByText("Giữ SOP hiện tại")).toBeInTheDocument();
    expect(screen.queryByText("Bác bỏ giả thuyết / bổ sung thông tin")).toBeNull();
  });
});

describe("DecisionPanel", () => {
  it("is locked until an approver from the list is chosen; revise needs a reason", () => {
    const onDecide = vi.fn();
    render(<DecisionPanel kind="proposal" proposalId="p1" approvers={APPROVERS} busy={false} onDecide={onDecide} />);
    expect(screen.getByTestId("decide-approved")).toBeDisabled();
    expect(screen.getByTestId("decide-rejected")).toBeDisabled();
    expect(screen.getByTestId("locked-hint")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("decide-approved"));
    expect(onDecide).not.toHaveBeenCalled();

    choose("alice");
    expect(screen.getByTestId("decide-approved")).toBeEnabled();
    expect(screen.getByTestId("decide-revise")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Lý do / thông tin bổ sung"), { target: { value: "  " } });
    expect(screen.getByTestId("decide-revise")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Lý do / thông tin bổ sung"), { target: { value: "M02 was serviced" } });
    fireEvent.click(screen.getByTestId("decide-revise"));
    expect(onDecide).toHaveBeenCalledWith({ decision: "revise", decided_by: "alice", reason: "M02 was serviced" });
  });

  it("falls back to a text field when the approver list could not be loaded, and checks names otherwise", () => {
    const { unmount } = render(<DecisionPanel kind="proposal" proposalId="p1" approvers={[]} busy={false} onDecide={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Người duyệt"), { target: { value: "anyone" } });
    expect(screen.getByTestId("decide-approved")).toBeEnabled(); // the backend check decides
    unmount();
    render(<DecisionPanel kind="proposal" proposalId="" approvers={APPROVERS} busy={false} onDecide={vi.fn()} />);
    choose("alice");
    expect(screen.getByTestId("decide-approved")).toBeDisabled(); // no proposal_id: nothing to bind the decision to
  });

  it("locks every button while a request runs", () => {
    render(<DecisionPanel kind="rollback" proposalId="r1" approvers={APPROVERS} busy onDecide={vi.fn()} />);
    choose("bob");
    expect(screen.getByTestId("decide-approved")).toBeDisabled();
    expect(screen.getByTestId("decide-rejected")).toBeDisabled();
  });
});

describe("HaltStage (FR-06.2)", () => {
  it("explains the reason in words and offers the backend options", () => {
    render(<HaltStage pending={stepStatus("run-halt-max-questions", 2).pending!} approvers={APPROVERS} busy={false} onDecide={vi.fn()} />);
    expect(screen.getByTestId("halt-reason")).toHaveTextContent("Đã hỏi đủ số lần cho phép");
    expect(screen.queryByTestId("sop-in-force")).toBeNull();
    expect(screen.getByText("Điều tra lại")).toBeInTheDocument();
    expect(screen.getByText("Kết thúc run")).toBeInTheDocument();
  });

  it("names the SOP in force after a declined rollback, and hides choices the backend does not offer", () => {
    const pending = { ...stepStatus("run-rollback-declined", 2).pending!, options: ["finish"] };
    render(<HaltStage pending={pending} approvers={APPROVERS} busy={false} onDecide={vi.fn()} />);
    expect(screen.getByTestId("halt-reason")).toHaveTextContent("Bạn đã giữ SOP hiện tại");
    expect(screen.getByTestId("sop-in-force")).toHaveTextContent(/SOP-RFL-001 v\d+/);
    expect(screen.queryByText("Điều tra lại")).toBeNull();
  });
});

describe("QuestionStage (FR-05)", () => {
  it("shows the question, the attempt and keeps Send locked while empty", () => {
    const model = buildRunModel(eventsUntilStep("run-happy", 0));
    const onAnswer = vi.fn();
    render(<QuestionStage pending={stepStatus("run-happy", 0).pending!} model={model} evidence={false} busy={false} onAnswer={onAnswer} />);
    expect(screen.getByTestId("pending-question")).toHaveTextContent("confidence 0.20");
    expect(screen.getByTestId("question-attempt")).toHaveTextContent("Lần hỏi 1/2");
    expect(screen.getByTestId("answer-submit")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Câu trả lời của bạn"), { target: { value: "lot B" } });
    fireEvent.click(screen.getByTestId("answer-submit"));
    expect(onAnswer).toHaveBeenCalledWith("lot B");
  });

  it("insufficient evidence after the change shows its own title and the measurement", () => {
    const model = buildRunModel(recording("run-insufficient-evidence").events);
    render(<QuestionStage pending={stepStatus("run-insufficient-evidence", 1).pending!} model={model} evidence busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByTestId("stage-title")).toHaveTextContent("Chưa đủ dữ liệu sau thay đổi");
    expect(screen.getByTestId("measure-insufficient")).toHaveTextContent("4 / 6");
  });
});

describe("MeasurementCard (FR-03)", () => {
  it("measured: big before/after, verdict and samples", () => {
    const m = buildRunModel(recording("run-happy").events).lastMeasurement!;
    render(<MeasurementCard m={m} />);
    expect(screen.getByTestId("measure-before")).toHaveTextContent("6,3%");
    expect(screen.getByTestId("measure-after")).toHaveTextContent("2,1%");
    expect(screen.getByTestId("measure-verdict")).toHaveTextContent("Đạt");
    expect(screen.getByTestId("measure-samples")).toHaveTextContent("21 điểm trước · 21 điểm sau");
  });

  it("not applied and missing fields never show null or passed=", () => {
    render(<MeasurementCard m={{ status: "not_applied", passed: null, reason: "proposal has no SOP change" }} />);
    expect(screen.getByTestId("measure-not-applied")).toHaveTextContent("Chưa áp dụng thay đổi");
    render(<MeasurementCard m={{ status: "measured" }} />);
    expect(document.body.textContent).not.toMatch(/null|undefined|NaN|passed=/);
  });
});

describe("ErrorStage and OutcomeStage (FR-04)", () => {
  it("Retry only when retryable; short message without traceback", () => {
    const onRetry = vi.fn();
    const { unmount } = render(<ErrorStage message={"RuntimeError: 529 overloaded\nTraceback..."} retryable busy={false} onRetry={onRetry} />);
    expect(screen.getByTestId("run-error-message")).toHaveTextContent(/^RuntimeError: 529 overloaded$/);
    fireEvent.click(screen.getByTestId("retry-button"));
    expect(onRetry).toHaveBeenCalled();
    unmount();
    render(<ErrorStage message="x" retryable={false} busy={false} onRetry={onRetry} />);
    expect(screen.queryByTestId("retry-button")).toBeNull();
    expect(screen.getByTestId("not-retryable")).toBeInTheDocument();
  });

  it("completed shows the kaizen card; no anomaly and closed have their own words", () => {
    const { unmount } = render(<OutcomeStage phase="completed" model={buildRunModel(recording("run-happy").events)} />);
    expect(screen.getByTestId("stage-title")).toHaveTextContent("Vòng cải tiến đã khép lại");
    expect(screen.getByTestId("kaizen-outcome")).toHaveTextContent("Thành công");
    unmount();
    const { unmount: u2 } = render(<OutcomeStage phase="no_anomaly" model={buildRunModel(recording("run-no-anomaly").events)} />);
    expect(screen.getByTestId("stage-title")).toHaveTextContent("Không phát hiện bất thường");
    u2();
    render(<OutcomeStage phase="closed" model={buildRunModel([])} />);
    expect(screen.getByTestId("stage-title")).toHaveTextContent("Run đã được đóng");
  });
});
