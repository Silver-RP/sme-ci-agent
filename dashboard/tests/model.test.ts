import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { describeEvent } from "@/lib/describe";
import { diffLines, diffStats } from "@/lib/diff";
import { dateTime, deltaPts, paramLabel, pct, shortError } from "@/lib/format";
import { RECORDINGS } from "@/lib/recordings";
import { chunksOf, visibleEvents } from "@/lib/replay";
import { buildRunModel, phaseOf, stepStates } from "@/lib/runModel";
import { eventsUntilStep, recording, stepStatus } from "./helpers";

describe("format", () => {
  it("never prints null, undefined or NaN", () => {
    for (const v of [null, undefined, Number.NaN, "x", {}]) {
      expect(pct(v)).toBe("–");
      expect(dateTime(v)).not.toMatch(/null|undefined|NaN/);
    }
    expect(pct(0.0619)).toBe("6,2%");
    expect(deltaPts(0.0629, 0.0206)).toBe("−4,2 điểm %");
    expect(dateTime("2026-03-10T22:00:00")).toBe("10/03/2026 22:00");
    expect(paramLabel("zone3_setpoint_c")).toEqual({ label: "Nhiệt độ vùng 3", unit: "°C" });
    expect(paramLabel("other")).toEqual({ label: "other", unit: "" });
    expect(shortError("RuntimeError: boom\n  File x.py, line 3")).toBe("RuntimeError: boom");
  });
});

describe("diffLines", () => {
  it("marks added and removed lines and detects no change", () => {
    const d = diffLines("a\nb\nc", "a\nc\nd");
    expect(d).toEqual([
      { kind: "same", text: "a" },
      { kind: "del", text: "b" },
      { kind: "same", text: "c" },
      { kind: "add", text: "d" },
    ]);
    expect(diffStats(d)).toEqual({ added: 1, removed: 1, changed: true });
    expect(diffStats(diffLines("x\ny\n", "x\r\ny")).changed).toBe(false);
    expect(diffLines("", "new")).toEqual([{ kind: "add", text: "new" }]);
  });
});

describe("run model on real recordings", () => {
  it("happy: waits for an answer, then the proposal, then completes with learning", () => {
    const m0 = buildRunModel(eventsUntilStep("run-happy", 0));
    expect(phaseOf(stepStatus("run-happy", 0), m0, { started: true, busy: false })).toBe("answer");
    expect(m0.question).toEqual({ attempt: 1, max: 2 });
    expect(m0.anomaly?.machine).toBe("M02");

    const m1 = buildRunModel(eventsUntilStep("run-happy", 1));
    expect(phaseOf(stepStatus("run-happy", 1), m1, { started: true, busy: false })).toBe("proposal");
    expect(m1.hypotheses[0]).toMatchObject({ group: "machine", description: "wrong_setpoint", confidence: 0.8 });
    expect(stepStates("proposal", m1)).toMatchObject({ detect: "done", investigate: "done", ask: "done", improve: "active", act: "todo" });

    const m2 = buildRunModel(recording("run-happy").events);
    expect(phaseOf(stepStatus("run-happy", 2), m2, { started: true, busy: false })).toBe("completed");
    expect(m2.learning).not.toBeNull();
    expect(stepStates("completed", m2)).toMatchObject({ learn: "done", measure: "done", rollback: "todo" });
  });

  it("insufficient evidence: the question comes from Measure", () => {
    const r = recording("run-insufficient-evidence");
    const m = buildRunModel(r.events);
    expect(m.evidenceAsk).toBe(true);
    expect(phaseOf(stepStatus("run-insufficient-evidence", 1), m, { started: true, busy: false })).toBe("evidence");
    expect(stepStates("evidence", m).measure).toBe("active");
  });

  it("rollback, halt, error and no anomaly map to their own phases", () => {
    const rb = buildRunModel(eventsUntilStep("run-rollback", 1));
    expect(phaseOf(stepStatus("run-rollback", 1), rb, { started: true, busy: false })).toBe("rollback");
    expect(rb.lastMeasurement?.passed).toBe(false);

    const halt = buildRunModel(recording("run-halt-max-questions").events);
    expect(phaseOf(stepStatus("run-halt-max-questions", 2), halt, { started: true, busy: false })).toBe("halt");

    expect(phaseOf(stepStatus("run-error-retry", 0), buildRunModel([]), { started: true, busy: false })).toBe("error");

    const none = buildRunModel(recording("run-no-anomaly").events);
    expect(phaseOf(stepStatus("run-no-anomaly", 0), none, { started: true, busy: false })).toBe("no_anomaly");
  });

  it("busy wins, and an unstarted run shows the start screen", () => {
    expect(phaseOf(null, buildRunModel([]), { started: false, busy: false })).toBe("start");
    expect(phaseOf(null, buildRunModel([]), { started: false, busy: true })).toBe("thinking");
  });

  it("describes every event of every recording without raw nulls or JSON", () => {
    for (const r of RECORDINGS) {
      for (const e of r.events) {
        const text = describeEvent(e);
        expect(text, `${r.name} ${e.type}`).not.toMatch(/null|undefined|NaN|\[object|\{"/);
      }
    }
  });

  it("tolerates payloads with missing fields (NFR-6)", () => {
    const happy = recording("run-happy").events;
    const stripped = happy.map((e) => ({ ...e, payload: {} }));
    const m = buildRunModel(stripped);
    expect(m.hypotheses).toEqual([]);
    for (const e of stripped) expect(describeEvent(e)).not.toMatch(/null|undefined|NaN/);
  });
});

describe("replay chunks", () => {
  it("one chunk per recorded step; the error before a retry stays in the stream (H-13)", () => {
    for (const r of RECORDINGS) {
      if (!r.steps) continue;
      const chunks = chunksOf(r);
      expect(chunks).toHaveLength(r.steps.filter((s) => s.http < 400).length);
    }
    const chunks = chunksOf(recording("run-error-retry"));
    expect(chunks[0].events.at(-1)?.type).toBe("run_finished");
    expect(chunks[0].status?.state).toBe("error");
    const after = visibleEvents(chunks, 2, chunks[2].events.length);
    expect(after.some((e) => e.type === "run_finished" && e.payload.status === "error")).toBe(true);
    expect(after.at(-1)?.payload.status).toBe("completed");
  });

  it("an error followed by more events is no longer the run's end (retry, H-13)", () => {
    const events = recording("run-error-retry").events;
    const errorAt = events.findIndex((e) => e.type === "run_finished");
    expect(buildRunModel(events.slice(0, errorAt + 1)).finished?.status).toBe("error");
    expect(buildRunModel(events.slice(0, errorAt + 2)).finished).toBeNull();
    expect(buildRunModel(events).finished?.status).toBe("completed");
  });

  it("replaying all chunks gives back the final stream", () => {
    const r = recording("run-rollback");
    const chunks = chunksOf(r);
    const last = chunks.length - 1;
    expect(visibleEvents(chunks, last, chunks[last].events.length).map((e) => e.event_id)).toEqual(r.events.map((e) => e.event_id));
  });
});

describe("bundled recordings", () => {
  it("are identical to docs/schema/examples (copy them again after export_fixtures.py)", () => {
    const docs = path.resolve(__dirname, "../../docs/schema/examples");
    const local = path.resolve(__dirname, "../fixtures/examples");
    const names = fs.readdirSync(docs).filter((f) => f.endsWith(".json")).sort();
    expect(fs.readdirSync(local).filter((f) => f.endsWith(".json")).sort()).toEqual(names);
    for (const f of names) {
      expect(fs.readFileSync(path.join(local, f), "utf-8"), f).toBe(fs.readFileSync(path.join(docs, f), "utf-8"));
    }
  });
});
