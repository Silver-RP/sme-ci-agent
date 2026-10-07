import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnomalyTable } from "@/components/AnomalyTable";
import { Timeline } from "@/components/Timeline";
import { sortByTime, summarizePayload, toAnomalyRows, type AgentEvent } from "@/lib/events";
import scenario1 from "@/fixtures/scenario1.json";

const events = scenario1 as unknown as AgentEvent[];

describe("AnomalyTable", () => {
  it("renders one row per anomaly_detected event with its fields", () => {
    render(<AnomalyTable events={events} />);
    const rows = screen.getAllByTestId("anomaly-row");
    expect(rows).toHaveLength(1);
    for (const text of ["defect_rate", "0.062", "0.02", "M02", "night", "manufacturing"]) {
      expect(within(rows[0]).getByText(text)).toBeInTheDocument();
    }
  });

  it("shows empty state for empty input", () => {
    render(<AnomalyTable events={[]} />);
    expect(screen.queryAllByTestId("anomaly-row")).toHaveLength(0);
    expect(screen.getByText(/no anomalies/i)).toBeInTheDocument();
  });

  it("tolerates missing payload fields", () => {
    const e = { ...events[0], payload: {} };
    expect(toAnomalyRows([e])[0]).toMatchObject({ kpi: "", value: null, baseline: null });
  });
});

describe("Timeline", () => {
  it("renders every event in time order with agent label", () => {
    render(<Timeline events={[...events].reverse()} />);
    const items = screen.getAllByTestId("timeline-item");
    expect(items).toHaveLength(events.length);
    expect(within(items[0]).getByText("anomaly_detected")).toBeInTheDocument();
    expect(within(items[items.length - 1]).getByText("run_finished")).toBeInTheDocument();
    const labels = screen.getAllByTestId("agent-label").map((n) => n.textContent);
    expect(labels).toEqual(events.map((e) => e.agent));
  });

  it("shows empty state and does not leak between renders", () => {
    const { unmount } = render(<Timeline events={events} />);
    unmount();
    render(<Timeline events={[]} />);
    expect(screen.queryAllByTestId("timeline-item")).toHaveLength(0);
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });
});

describe("helpers", () => {
  it("sortByTime does not mutate input and is stable", () => {
    const input = [events[2], events[0], events[1]];
    const copy = [...input];
    expect(sortByTime(input).map((e) => e.event_id)).toEqual([events[0], events[1], events[2]].map((e) => e.event_id));
    expect(input).toEqual(copy);
  });

  it("summarizePayload handles empty and long payloads", () => {
    expect(summarizePayload({})).toBe("");
    expect(summarizePayload({ a: "x".repeat(500) }).length).toBeLessThanOrEqual(140);
    expect(summarizePayload({ kpi: "defect_rate", n: 1 })).toBe("kpi=defect_rate, n=1");
  });
});
