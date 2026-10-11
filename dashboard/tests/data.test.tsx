import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AuditPage from "@/app/audit/page";
import KaizenPage from "@/app/kaizen/page";
import OverviewPage from "@/app/overview/page";
import RunsPage from "@/app/runs/page";
import { describeAudit } from "@/lib/describe";
import { dateTime } from "@/lib/format";
import { describeVersions, focusAnomaly, lessonsOf, metricChange, recentMean, sopIdsOf, type AuditRow, type Metric, type SopVersion } from "@/lib/readApi";
import { recording, resp } from "./helpers";

// Shapes copied from the running backend (docs/schema/payloads.md §3).
const unavailable: Metric[] = [
  { name: "defect_rate", unit: "ratio", before: null, after: null, available: false, reason: "no finished run has saved a lesson with this KPI yet", run_id: null },
  { name: "mttd_mttr", unit: "hours", before: null, after: null, available: false, reason: "no real source yet (planned for R10b2)", run_id: null },
  { name: "recurrence_rate", unit: "ratio", before: null, after: null, available: false, reason: "no real source yet (planned for R10b2)", run_id: null },
];
const learned: Metric[] = [{ ...unavailable[0], before: 0.0629, after: 0.0196, available: true, reason: null, run_id: "run_fb118e36" }, ...unavailable.slice(1)];

const versions: SopVersion[] = [
  { version: 1, created_by: "config", run_id: null, created_at: null, content: "original" },
  { version: 2, created_by: "alice", run_id: "run_a", created_at: "2026-10-10T14:45:35+00:00", content: "changed" },
  { version: 3, created_by: "bob", run_id: "run_a", created_at: "2026-10-10T14:50:00+00:00", content: "original" },
];

const auditRows: AuditRow[] = [
  { id: 3, ts: "2026-10-10T14:45:35+00:00", run_id: "run_a", actor: "agent", action: "apply_sop", params: { sop_id: "SOP-RFL-001", base_version: 1 } },
  { id: 2, ts: "2026-10-10T14:45:34+00:00", run_id: "run_a", actor: "alice", action: "approval_decided", params: { kind: "proposal", decision: "approved", decided_by: "alice", reason: "demo check" } },
  { id: 1, ts: "2026-10-10T14:45:33+00:00", run_id: "run_a", actor: "agent", action: "correlate", params: { kpi: "defect_rate", machine_id: "M02" } },
];

/** Global fetch that answers by path; an Error value makes that call fail. */
function stubApi(routes: Record<string, unknown>) {
  const fn = vi.fn(async (url: string) => {
    const path = new URL(url).pathname;
    const key = Object.keys(routes).find((k) => path === k || path.startsWith(`${k}/`));
    if (!key) return resp(404, { detail: `no route ${path}` });
    const body = routes[key];
    if (body instanceof Error) throw body;
    return resp(200, typeof body === "function" ? body(path) : body);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("read API helpers", () => {
  it("labels SOP versions newest first: original, applied, restored by a rollback", () => {
    const out = describeVersions(versions);
    expect(out.map((v) => v.version)).toEqual([3, 2, 1]);
    expect(out.map((v) => v.origin)).toEqual([{ kind: "restored", from: 1 }, { kind: "applied" }, { kind: "config" }]);
  });

  it("finds SOP ids in the log and lessons in a run export", () => {
    expect(sopIdsOf(auditRows)).toEqual(["SOP-RFL-001"]);
    const lessons = lessonsOf(recording("run-happy").events);
    expect(lessons).toHaveLength(1);
    expect(lessons[0].outcome).toBe("success");
  });

  it("never computes a change for a metric without a real source", () => {
    expect(metricChange(unavailable[0])).toBeNull();
    expect(metricChange({ ...learned[0], before: 0 })).toBeNull();
    expect(metricChange(learned[0])).toBeCloseTo(-0.688, 3);
  });

  it("describes audit rows in words; read-only tool calls are their own group", () => {
    expect(describeAudit("approval_decided", auditRows[1].params)).toMatchObject({ label: "Duyệt đề xuất", tone: "ok", group: "decision" });
    expect(describeAudit("approval_decided", { kind: "proposal", decision: "sop_conflict", message: "SOP changed" })).toMatchObject({ tone: "bad", detail: "SOP changed" });
    expect(describeAudit("correlate", auditRows[2].params).group).toBe("read");
    expect(describeAudit("kpi_threshold_check", { kpi: "defect_rate", after: 0.0196, target: 0.02, passed: true }).tone).toBe("ok");
    expect(describeAudit("something_new", {}).label).toBe("something_new");
  });

  it("shows server stamps in local time and plant time as written", () => {
    expect(dateTime("2026-03-10T22:00:00")).toBe("10/03/2026 22:00");
    const d = new Date("2026-10-10T14:45:35+00:00");
    expect(dateTime("2026-10-10T14:45:35+00:00")).toBe(`10/10/2026 ${String(d.getHours()).padStart(2, "0")}:45`);
  });
});

describe("Runs page (GET /runs)", () => {
  it("a waiting run opens live to continue, a finished one opens read-only", async () => {
    stubApi({
      "/runs": {
        runs: [
          { run_id: "run_w", state: "waiting", started_at: "2026-10-10T09:00:00+00:00", finished_at: null, outcome: null, pending: { type: "approval", kind: "proposal", proposal_id: "p1" } },
          { run_id: "run_f", state: "finished", started_at: "2026-10-10T08:00:00+00:00", finished_at: "2026-10-10T08:00:05+00:00", outcome: "completed", pending: null },
        ],
      },
    });
    render(<RunsPage />);
    expect(await screen.findAllByTestId("run-row")).toHaveLength(2);
    expect(screen.getByText("Chờ bạn duyệt")).toBeInTheDocument();
    expect(screen.getByText("Hoàn tất, đã học")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tiếp tục/ })).toHaveAttribute("href", "/?source=live&run=run_w");
    expect(screen.getByRole("link", { name: /Xem lại/ })).toHaveAttribute("href", "/?source=sse&run=run_f");
  });

  it("backend down: shows the error and loads again on Retry", async () => {
    const fn = stubApi({ "/runs": new TypeError("Failed to fetch") });
    render(<RunsPage />);
    expect(await screen.findByTestId("data-error")).toHaveTextContent("Failed to fetch");
    stubApi({ "/runs": { runs: [] } });
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText("Chưa có run nào.")).toBeInTheDocument();
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe("Kaizen page (GET /metrics, run exports)", () => {
  it("metrics without a source show no number at all", async () => {
    stubApi({ "/metrics": { metrics: unavailable }, "/runs": { runs: [] } });
    render(<KaizenPage />);
    expect(await screen.findAllByTestId("metric-unavailable")).toHaveLength(3);
    for (const card of screen.getAllByTestId("metric-card")) expect(card.textContent).not.toMatch(/\d+%|null|NaN/);
    expect(await screen.findByText("Chưa có bài học nào.")).toBeInTheDocument();
  });

  it("a learned KPI shows before/after; its kaizen card comes from the run export", async () => {
    const happy = recording("run-happy");
    stubApi({
      "/metrics": { metrics: learned },
      "/runs": (path: string) =>
        path.endsWith("/export")
          ? { events: happy.events }
          : { runs: [{ run_id: "run_fb118e36", state: "finished", started_at: "", finished_at: "", outcome: "completed", pending: null }] },
    });
    render(<KaizenPage />);
    await screen.findAllByTestId("metric-card");
    const kpiCard = screen.getAllByTestId("metric-card")[0];
    expect(within(kpiCard).getByText("2,0%")).toBeInTheDocument();
    expect(within(kpiCard).getByText("6,3%")).toBeInTheDocument();
    expect(screen.getAllByTestId("metric-unavailable")).toHaveLength(2);
    expect(await screen.findByText(happy.events[0].run_id)).toBeInTheDocument();
  });
});

describe("Audit page (GET /audit, /sop/{id}/versions)", () => {
  it("hides read-only tool calls until asked; lists the SOP versions found in the log", async () => {
    stubApi({ "/audit": { rows: auditRows }, "/sop": { sop_id: "SOP-RFL-001", versions } });
    render(<AuditPage />);
    expect(await screen.findAllByTestId("audit-row")).toHaveLength(2);
    // generic backend actors in words, approver names as they are
    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Hiện thao tác đọc dữ liệu"));
    expect(screen.getAllByTestId("audit-row")).toHaveLength(3);
    expect(await screen.findAllByTestId("sop-version")).toHaveLength(3);
    expect(screen.getByText("Khôi phục nội dung v1")).toBeInTheDocument();
    expect(screen.getByText("Bản gốc (config)")).toBeInTheDocument();
  });
});

describe("Overview page (GET /kpi/series)", () => {
  it("asks for the main KPI from /metrics, not a hard-coded name", async () => {
    const fn = stubApi({
      "/metrics": { metrics: [{ ...unavailable[0], name: "first_pass_yield" }] },
      "/kpi/series": { kpi: "first_pass_yield", machine: "M02", shift: null, points: [], baseline: 0.9, upper_limit: 0.95, anomalies: [] },
    });
    render(<OverviewPage />);
    await waitFor(() => expect(fn.mock.calls.some(([u]) => String(u).endsWith("/kpi/series?kpi=first_pass_yield"))).toBe(true));
    expect(await screen.findByText("90,0%")).toBeInTheDocument();
  });

  it("opens on the longest anomaly's machine and shift", async () => {
    const anomalies = [
      { start: "2026-06-02T22:00:00", end: "2026-06-30T22:00:00", machine: "M01", shift: "night" },
      { start: "2026-03-10T22:00:00", end: "2026-06-30T22:00:00", machine: "M02", shift: "night" },
    ];
    const fn = stubApi({
      "/metrics": { metrics: unavailable },
      "/kpi/series": { kpi: "defect_rate", machine: null, shift: null, points: [], baseline: null, upper_limit: null, anomalies },
    });
    render(<OverviewPage />);
    await waitFor(() => expect(fn.mock.calls.some(([u]) => String(u).includes("machine=M02&shift=night"))).toBe(true));
  });
});

describe("overview numbers", () => {
  it("averages the last 7 days by time, not the last 7 points", () => {
    // three points a day: the last 7 points cover only ~2 days
    const points = Array.from({ length: 30 }, (_, i) => ({
      ts: new Date(Date.UTC(2026, 0, 1) + i * 8 * 3600_000).toISOString().slice(0, 19),
      value: i < 9 ? 0.1 : 0.02,
    }));
    expect(recentMean(points, 7)).toBeCloseTo(0.02, 5);
    expect(recentMean([], 7)).toBeNull();
    expect(focusAnomaly([])).toBeNull();
  });
});
