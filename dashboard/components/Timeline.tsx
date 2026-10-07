import { sortByTime, summarizePayload, type AgentEvent } from "@/lib/events";

export function Timeline({ events }: { events: readonly AgentEvent[] }) {
  const sorted = sortByTime(events);
  return (
    <section aria-label="Trace timeline">
      <h2>Trace timeline</h2>
      {sorted.length === 0 ? (
        <p className="muted">No events yet.</p>
      ) : (
        <ol className="timeline">
          {sorted.map((e) => (
            <li key={e.event_id} data-testid="timeline-item">
              <time dateTime={e.ts}>{e.ts.slice(11, 19)}</time>
              <span className="badge" data-testid="agent-label">
                {e.agent}
              </span>
              <strong>{e.type}</strong>
              <span className="muted">
                {e.domain} {summarizePayload(e.payload)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
