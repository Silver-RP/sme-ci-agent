import fs from "node:fs";
import path from "node:path";
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import scenario1 from "@/fixtures/scenario1.json";

const schema = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, "../../docs/schema/events.json"), "utf-8"),
);
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
const validate = ajv.compile(schema);

const events = scenario1 as unknown as Record<string, unknown>[];

describe("scenario1 fixture vs events.json", () => {
  it("every event is valid", () => {
    for (const e of events) {
      expect(validate(e), JSON.stringify(validate.errors)).toBe(true);
    }
  });

  it("covers the loop from anomaly_detected to run_finished", () => {
    expect(events[0].type).toBe("anomaly_detected");
    expect(events[events.length - 1].type).toBe("run_finished");
    const types = new Set(events.map((e) => e.type));
    for (const t of ["question_asked", "answer_received", "proposal_created", "approval_decided", "sop_applied", "kpi_measured", "learning_saved"]) {
      expect(types.has(t)).toBe(true);
    }
  });

  it.each(["agent", "domain"])("missing %s makes validation fail", (field) => {
    const broken = { ...events[0] };
    delete broken[field];
    expect(validate(broken)).toBe(false);
  });

  it("rejects unknown agent and empty object", () => {
    expect(validate({ ...events[0], agent: "robot" })).toBe(false);
    expect(validate({})).toBe(false);
  });

  it("has unique event ids", () => {
    expect(new Set(events.map((e) => e.event_id)).size).toBe(events.length);
  });
});
