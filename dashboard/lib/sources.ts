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
  /** `lastEventId` is the SSE `id:` of the event (1-based index in the backend's event list) */
  addEventListener(type: string, listener: (ev: { data: unknown; lastEventId?: string }) => void): void;
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
  /** pause before reopening the stream while a retryable error waits for Retry */
  reopenMs?: number;
}

/** run_finished with status "error" that the backend can still retry (payloads.md §2: retryable true or absent). */
function isRetryableError(data: unknown): boolean {
  try {
    const e = typeof data === "string" ? JSON.parse(data) : data;
    const p = e && typeof e === "object" ? (e as { payload?: { status?: unknown; retryable?: unknown } }).payload : undefined;
    return p?.status === "error" && p.retryable !== false;
  } catch {
    return false;
  }
}

/**
 * SSE client for GET /runs/{id}/events (named events, one per event type). Bounded retries for real connection
 * loss; the stream stays open across a retryable error and closes when the run really ends.
 */
export function createSseSource(runId: string, opts: SseOptions = {}): EventSourceAdapter {
  const base = (opts.baseUrl ?? apiBase()).replace(/\/$/, "");
  const maxRetries = opts.maxRetries ?? 3;
  const reopenMs = opts.reopenMs ?? 2000;
  const url = `${base}/runs/${encodeURIComponent(runId)}/events?follow=true`;
  let es: EventSourceLike | null = null;
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  return {
    start(h) {
      stopped = false;
      let retries = 0;
      // A retryable error is not the end of the run (H-46): someone may press Retry, here or in another tab.
      // The backend ends the stream while the run is in error, so the stream is reopened from the last SSE id
      // with `after=` (FR-04.3): the events after the Retry arrive in order, without duplicates. Browsers do not
      // reliably send Last-Event-ID on their own reconnect (Chrome did not in our test), so it is not relied on.
      let awaitingRetry = false;
      let lastId = 0;
      const Ctor = opts.ctor ?? (globalThis as { EventSource?: EventSourceCtor }).EventSource;
      if (!Ctor) {
        h.onStatus("disconnected", "EventSource is not available");
        return;
      }

      const connect = () => {
        const src = new Ctor(lastId > 0 ? `${url}&after=${lastId}` : url);
        es = src;
        src.onopen = () => {
          retries = 0;
          h.onStatus("open");
        };
        for (const t of EVENT_TYPES) {
          src.addEventListener(t, (ev) => {
            if (src !== es) return;
            const id = Number(ev.lastEventId);
            if (Number.isInteger(id) && id > lastId) lastId = id;
            h.onEvent(ev.data);
            if (t !== "run_finished") {
              awaitingRetry = false;
              return;
            }
            if (isRetryableError(ev.data)) {
              awaitingRetry = true;
              return;
            }
            stopped = true;
            src.close();
            h.onStatus("closed");
          });
        }
        src.onerror = () => {
          if (stopped || src !== es) return;
          // the stream ended while waiting for Retry (not a fatal error such as a 404): reopen it from lastId;
          // expected, so it does not count against maxRetries
          if (awaitingRetry && src.readyState !== CLOSED) {
            src.close();
            es = null; // detach: late callbacks of this stream are ignored by the `src !== es` guards
            timer = setTimeout(() => {
              if (!stopped) connect();
            }, reopenMs);
            return;
          }
          retries += 1;
          if (retries > maxRetries || src.readyState === CLOSED) {
            stopped = true;
            src.close();
            h.onStatus("disconnected", `connection lost after ${retries} attempt(s)`);
          } else {
            h.onStatus("connecting", `reconnecting (${retries}/${maxRetries})`);
          }
        };
      };

      h.onStatus("connecting");
      connect();
    },
    close() {
      stopped = true;
      if (timer) clearTimeout(timer);
      timer = null;
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
