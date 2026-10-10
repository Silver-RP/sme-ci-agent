import type { Decision } from "@/lib/api";

export type DecisionInput = Pick<Decision, "decision" | "decided_by" | "reason">;

/** What a stage can ask the controller (live backend or replay) to do. */
export interface RunActions {
  start?: (changeTime: string) => void;
  answer: (text: string) => void;
  decide: (proposalId: string, kind: Decision["kind"], d: DecisionInput) => void;
  retry: () => void;
  /** close a run whose error can no longer be retried (live only, POST /runs/{id}/close, H-48) */
  close?: (closedBy: string, reason: string) => void;
  reset?: () => void;
}

export type RunMode = "live" | "replay" | "watch";
