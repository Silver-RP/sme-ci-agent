import { EVENT_TYPES } from "@/lib/events";

export type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "disconnected";

export interface SourceHandlers {
  /** Raw (unvalidated) event: object or JSON string. Validation is done by the consumer. */
  onEvent: (raw: unknown) => void;
  onStatus: (status: ConnectionStatus, detail?: string) => void;
}

/** Common interface of the SSE client and the fixture replayer. */
export interface EventSourceAdapter {
  start(handlers: SourceHandlers): void;
  close(): void;
}

export interface EventSourceLike {
  readyState: number;
  onopen: ((ev: unknown) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  addEventListener(type: string, listener: (ev: { data: unknown }) => void): void;
  close(): void;
}
export type EventSourceCtor = new (url: string) => EventSourceLike;

const CLOSED = 2;

export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export interface SseOptions {
  baseUrl?: string;
  maxRetries?: number;
  ctor?: EventSourceCtor;
}

/** SSE client for GET /runs/{id}/events (named events, one per event type). Bounded retries. */
export function createSseSource(runId: string, opts: SseOptions = {}): EventSourceAdapter {
  const base = (opts.baseUrl ?? apiBase()).replace(/\/$/, "");
  const maxRetries = opts.maxRetries ?? 3;
  const url = `${base}/runs/${encodeURIComponent(runId)}/events?follow=true`;
  let es: EventSourceLike | null = null;
  let stopped = false;

  return {
    start(h) {
      stopped = false;
      let retries = 0;
      const Ctor = opts.ctor ?? (globalThis as { EventSource?: EventSourceCtor }).EventSource;
      if (!Ctor) {
        h.onStatus("disconnected", "EventSource is not available");
        return;
      }
      h.onStatus("connecting");
      es = new Ctor(url);
      const src = es;
      src.onopen = () => {
        retries = 0;
        h.onStatus("open");
      };
      for (const t of EVENT_TYPES) {
        src.addEventListener(t, (ev) => {
          h.onEvent(ev.data);
          if (t === "run_finished") {
            stopped = true;
            src.close();
            h.onStatus("closed");
          }
        });
      }
      src.onerror = () => {
        if (stopped) return;
        retries += 1;
        if (retries > maxRetries || src.readyState === CLOSED) {
          stopped = true;
          src.close();
          h.onStatus("disconnected", `connection lost after ${retries} attempt(s)`);
        } else {
          h.onStatus("connecting", `reconnecting (${retries}/${maxRetries})`);
        }
      };
    },
    close() {
      stopped = true;
      es?.close();
      es = null;
    },
  };
}

/** Replays a fixture one event at a time with the same interface as the SSE client. */
export function createFixtureSource(
  events: readonly unknown[],
  opts: { intervalMs?: number } = {},
): EventSourceAdapter {
  const interval = opts.intervalMs ?? 400;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let token = 0;

  return {
    start(h) {
      this.close();
      const my = ++token;
      let i = 0;
      h.onStatus("open");
      const tick = () => {
        if (my !== token) return;
        if (i >= events.length) {
          h.onStatus("closed");
          return;
        }
        h.onEvent(events[i++]);
        timer = setTimeout(tick, interval);
      };
      timer = setTimeout(tick, 0);
    },
    close() {
      token++;
      if (timer) clearTimeout(timer);
      timer = null;
    },
  };
}
