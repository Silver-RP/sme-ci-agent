"use client";

import { useEffect, useReducer } from "react";
import type { AgentEvent } from "@/lib/events";
import { parseEventData } from "@/lib/validate";
import type { ConnectionStatus, EventSourceAdapter } from "@/lib/sources";

export interface RunState {
  events: AgentEvent[];
  errors: string[];
  status: ConnectionStatus;
  detail?: string;
}

export type RunAction =
  | { kind: "raw"; raw: unknown }
  | { kind: "status"; status: ConnectionStatus; detail?: string }
  | { kind: "reset" };

export const initialRunState: RunState = { events: [], errors: [], status: "idle" };

export function runReducer(state: RunState, a: RunAction): RunState {
  switch (a.kind) {
    case "reset":
      return { events: [], errors: [], status: "idle" };
    case "status":
      return { ...state, status: a.status, detail: a.detail };
    case "raw": {
      const r = parseEventData(a.raw);
      if (!r.ok) return { ...state, errors: [...state.errors, r.error] };
      if (state.events.some((e) => e.event_id === r.event.event_id)) return state;
      return { ...state, events: [...state.events, r.event] };
    }
  }
}

/** Feeds events from any source (SSE or fixture) into one state. Invalid events become errors. */
export function useRunEvents(makeSource: () => EventSourceAdapter | null, deps: unknown[]): RunState {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  useEffect(() => {
    dispatch({ kind: "reset" });
    const src = makeSource();
    src?.start({
      onEvent: (raw) => dispatch({ kind: "raw", raw }),
      onStatus: (status, detail) => dispatch({ kind: "status", status, detail }),
    });
    return () => src?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
