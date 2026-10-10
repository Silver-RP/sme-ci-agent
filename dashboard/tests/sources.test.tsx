import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EVENT_TYPES } from "@/lib/events";
import {
  createFixtureSource,
  createSseSource,
  type EventSourceAdapter,
  type EventSourceLike,
  type SourceHandlers,
} from "@/lib/sources";
import { validateEvent } from "@/lib/validate";
import { useRunEvents } from "@/lib/useRunEvents";
import scenario1 from "@/fixtures/scenario1.json";

const fixture = scenario1 as unknown as Record<string, unknown>[];

class FakeES implements EventSourceLike {
  static last: FakeES;
  readyState = 0;
  onopen: ((ev: unknown) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  listeners: Record<string, ((ev: { data: unknown }) => void)[]> = {};
  closed = false;
  constructor(public url: string) {
    FakeES.last = this;
  }
  addEventListener(t: string, l: (ev: { data: unknown }) => void) {
    (this.listeners[t] ??= []).push(l);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  emit(ev: unknown) {
    const e = ev as { type: string };
    this.listeners[e.type]?.forEach((l) => l({ data: JSON.stringify(ev) }));
  }
  emitRaw(type: string, data: string) {
    this.listeners[type]?.forEach((l) => l({ data }));
  }
}

/** Minimal consumer of useRunEvents (the run screen renders the same state with more styling). */
function RunView({ makeSource }: { title?: string; sourceKey?: string; makeSource: () => EventSourceAdapter | null }) {
  const s = useRunEvents(makeSource, ["k"]);
  return (
    <div>
      <span data-testid="connection-status" data-status={s.status} />
      {s.events.map((e) => (
        <i key={e.event_id} data-testid="timeline-item">
          {e.type}
        </i>
      ))}
      {s.errors.length > 0 && <p data-testid="event-errors">{s.errors.length} invalid event(s)</p>}
    </div>
  );
}

function recorder() {
  const raws: unknown[] = [];
  const statuses: string[] = [];
  const h: SourceHandlers = {
    onEvent: (r) => raws.push(r),
    onStatus: (s) => statuses.push(s),
  };
  return { raws, statuses, h };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("same interface", () => {
  it("fixture replayer and SSE client both deliver events and statuses through SourceHandlers", () => {
    const sources: EventSourceAdapter[] = [
      createFixtureSource(fixture, { intervalMs: 10 }),
      createSseSource("run_x", { ctor: FakeES }),
    ];
    for (const s of sources) {
      const r = recorder();
      s.start(r.h);
      if (s === sources[1]) {
        FakeES.last.onopen?.({});
        FakeES.last.emit(fixture[0]);
      } else {
        vi.advanceTimersByTime(5);
      }
      expect(r.raws.length).toBeGreaterThanOrEqual(1);
      expect(r.statuses).toContain("open");
      s.close();
    }
  });

  it("sse uses the API URL and listens to every event type", () => {
    createSseSource("run 1", { baseUrl: "http://api.test/", ctor: FakeES }).start(recorder().h);
    expect(FakeES.last.url).toBe("http://api.test/runs/run%201/events?follow=true");
    expect(Object.keys(FakeES.last.listeners).sort()).toEqual([...EVENT_TYPES].sort());
  });

  it("fixture replay is repeatable and stops after close", () => {
    const s = createFixtureSource(fixture, { intervalMs: 10 });
    const a = recorder();
    s.start(a.h);
    vi.advanceTimersByTime(10_000);
    expect(a.raws).toHaveLength(fixture.length);
    expect(a.statuses.at(-1)).toBe("closed");
    const b = recorder();
    s.start(b.h);
    s.close();
    vi.advanceTimersByTime(10_000);
    expect(b.raws.length).toBeLessThan(2);
  });

  it("empty fixture closes without events", () => {
    const r = recorder();
    createFixtureSource([]).start(r.h);
    vi.advanceTimersByTime(10);
    expect(r.raws).toEqual([]);
    expect(r.statuses.at(-1)).toBe("closed");
  });
});

describe("validateEvent", () => {
  it("accepts fixture, rejects bad shapes", () => {
    expect(fixture.every((e) => validateEvent(e).ok)).toBe(true);
    const e = fixture[0];
    const { agent: _a, ...noAgent } = e;
    const { domain: _d, ...noDomain } = e;
    void _a;
    void _d;
    for (const bad of [null, [], "x", {}, noAgent, noDomain, { ...e, agent: "robot" }, { ...e, type: "nope" }, { ...e, ts: "abc" }, { ...e, payload: null }, { ...e, extra: 1 }]) {
      expect(validateEvent(bad).ok).toBe(false);
    }
  });
});

describe("RunView with SSE", () => {
  const view = () =>
    render(
      <RunView
        title="t"
        sourceKey="k"
        makeSource={() => createSseSource("r1", { ctor: FakeES, maxRetries: 2 })}
      />,
    );

  it("updates the timeline progressively and ignores invalid events with a visible error", () => {
    view();
    act(() => FakeES.last.onopen?.({}));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "open");
    act(() => FakeES.last.emit(fixture[0]));
    expect(screen.getAllByTestId("timeline-item")).toHaveLength(1);
    act(() => FakeES.last.emitRaw("tool_called", "{not json"));
    act(() => FakeES.last.emit({ ...fixture[1], agent: undefined }));
    act(() => FakeES.last.emit({ ...fixture[1], domain: undefined }));
    expect(screen.getAllByTestId("timeline-item")).toHaveLength(1);
    expect(screen.getByTestId("event-errors")).toHaveTextContent("3 invalid event(s)");
    act(() => FakeES.last.emit(fixture[1]));
    act(() => FakeES.last.emit(fixture[1])); // duplicate after reconnect
    expect(screen.getAllByTestId("timeline-item")).toHaveLength(2);
  });

  it("shows disconnected after bounded retries and stops retrying", () => {
    view();
    const es = FakeES.last;
    act(() => es.onerror?.({}));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "connecting");
    act(() => es.onerror?.({}));
    act(() => es.onerror?.({}));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "disconnected");
    expect(es.closed).toBe(true);
    act(() => es.onerror?.({}));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "disconnected");
  });

  it("successful open resets the retry counter; run_finished closes", () => {
    view();
    const es = FakeES.last;
    act(() => es.onerror?.({}));
    act(() => es.onerror?.({}));
    act(() => es.onopen?.({}));
    act(() => es.onerror?.({}));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "connecting");
    const fin = fixture[fixture.length - 1];
    act(() => es.emit(fin));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "closed");
    expect(es.closed).toBe(true);
  });

  it("reports missing EventSource instead of crashing", () => {
    render(<RunView title="t" sourceKey="k" makeSource={() => createSseSource("r1", { ctor: undefined })} />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "disconnected");
  });
});

describe("RunView with fixture", () => {
  it("fills the timeline from first to last event", () => {
    render(
      <RunView title="t" sourceKey="f" makeSource={() => createFixtureSource(fixture, { intervalMs: 5 })} />,
    );
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    const items = screen.getAllByTestId("timeline-item");
    expect(items).toHaveLength(fixture.length);
    expect(items[0]).toHaveTextContent("anomaly_detected");
    expect(items.at(-1)).toHaveTextContent("run_finished");
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "closed");
    expect(screen.queryByTestId("event-errors")).toBeNull();
  });
});
