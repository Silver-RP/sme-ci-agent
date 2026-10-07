import { toAnomalyRows, type AgentEvent } from "@/lib/events";

export function AnomalyTable({ events }: { events: readonly AgentEvent[] }) {
  const rows = toAnomalyRows(events);
  return (
    <section aria-label="Anomalies">
      <h2>Anomalies</h2>
      {rows.length === 0 ? (
        <p className="muted">No anomalies detected.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Domain</th>
              <th>KPI</th>
              <th>Value</th>
              <th>Baseline</th>
              <th>Machine</th>
              <th>Shift</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.eventId} data-testid="anomaly-row">
                <td>{r.ts}</td>
                <td>{r.domain}</td>
                <td>{r.kpi}</td>
                <td>{r.value ?? "-"}</td>
                <td>{r.baseline ?? "-"}</td>
                <td>{r.machine}</td>
                <td>{r.shift}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
