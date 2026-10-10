// Recorded runs bundled with the dashboard, for replay without a backend (FR-07).
// fixtures/examples/ is a copy of docs/schema/examples/ (tests/recordings.test.ts fails if they drift);
// regenerate both with `uv run python scripts/export_fixtures.py`, then copy the files here.

import type { AgentEvent } from "@/lib/events";
import type { Recording, RecordedStep } from "@/lib/replay";
import happy from "@/fixtures/examples/run-happy.json";
import rollback from "@/fixtures/examples/run-rollback.json";
import rollbackDeclined from "@/fixtures/examples/run-rollback-declined.json";
import insufficient from "@/fixtures/examples/run-insufficient-evidence.json";
import revise from "@/fixtures/examples/run-revise.json";
import haltMaxQuestions from "@/fixtures/examples/run-halt-max-questions.json";
import errorRetry from "@/fixtures/examples/run-error-retry.json";
import noAnomaly from "@/fixtures/examples/run-no-anomaly.json";
import scenario1 from "@/fixtures/scenario1.json";

type Raw = { description?: string; steps?: unknown[]; events?: unknown[] };

function rec(name: string, raw: Raw | unknown[]): Recording {
  if (Array.isArray(raw)) return { name, events: raw as AgentEvent[] };
  return {
    name,
    description: raw.description,
    steps: (raw.steps ?? []) as RecordedStep[],
    events: (raw.events ?? []) as AgentEvent[],
  };
}

export const RECORDINGS: Recording[] = [
  rec("run-happy", happy),
  rec("run-rollback", rollback),
  rec("run-rollback-declined", rollbackDeclined),
  rec("run-insufficient-evidence", insufficient),
  rec("run-revise", revise),
  rec("run-halt-max-questions", haltMaxQuestions),
  rec("run-error-retry", errorRetry),
  rec("run-no-anomaly", noAnomaly),
  rec("scenario1", scenario1 as unknown[]),
];

export const DEFAULT_RECORDING = "run-happy";

export function findRecording(name: string | null | undefined): Recording {
  return RECORDINGS.find((r) => r.name === name) ?? RECORDINGS.find((r) => r.name === DEFAULT_RECORDING)!;
}

/** Synthetic approver names (same allow-list as data/context_profile.yaml), used when replaying offline. */
export const REPLAY_APPROVERS = ["alice", "bob", "qa_lead"];
