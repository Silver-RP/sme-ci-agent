"use client";

import { AnomalyTable } from "@/components/AnomalyTable";
import { Timeline } from "@/components/Timeline";
import type { EventSourceAdapter } from "@/lib/sources";
import { useRunEvents } from "@/lib/useRunEvents";

export function RunView({
  title,
  makeSource,
  sourceKey,
}: {
  title: string;
  makeSource: () => EventSourceAdapter | null;
  sourceKey: string;
}) {
  const { events, errors, status, detail } = useRunEvents(makeSource, [sourceKey]);
  return (
    <main>
      <h1>SME CI Agent</h1>
      <p className="muted">{title}</p>
      <p role="status" data-testid="connection-status" data-status={status}>
        Connection: {status}
        {detail ? ` (${detail})` : ""}
      </p>
      {errors.length > 0 && (
        <div role="alert" data-testid="event-errors">
          {errors.length} invalid event(s) ignored:
          <ul>
            {errors.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      <AnomalyTable events={events} />
      <Timeline events={events} />
    </main>
  );
}
