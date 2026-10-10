import { fireEvent, screen } from "@testing-library/react";
import type { RunStatus } from "@/lib/api";
import type { AgentEvent } from "@/lib/events";
import { findRecording } from "@/lib/recordings";

/** Real recording (docs/schema/examples/run-<name>.json). */
export function recording(name: string) {
  const r = findRecording(name);
  if (r.name !== name) throw new Error(`no recording ${name}`);
  return r;
}

/** Run status returned by step `i` of a recording. */
export function stepStatus(name: string, i: number): RunStatus {
  return recording(name).steps![i].response as RunStatus;
}

/** Events of a recording up to (and including) the last event of step `i`. */
export function eventsUntilStep(name: string, i: number): AgentEvent[] {
  const r = recording(name);
  const last = r.steps![i].last_event as AgentEvent;
  const idx = r.events.findIndex((e) => e.event_id === last.event_id && e.type === last.type);
  return idx >= 0 ? r.events.slice(0, idx + 1) : [...r.events];
}

/** Picks an option of a Radix Select (components/ui/select.tsx): open it from the keyboard, click the option. */
export function chooseOption(label: string, option: string) {
  fireEvent.keyDown(screen.getByLabelText(label), { key: "Enter" });
  fireEvent.click(screen.getByRole("option", { name: option }));
}

export function resp(status: number, body: unknown): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}
