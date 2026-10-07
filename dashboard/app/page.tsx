import { AnomalyTable } from "@/components/AnomalyTable";
import { Timeline } from "@/components/Timeline";
import type { AgentEvent } from "@/lib/events";
import scenario1 from "@/fixtures/scenario1.json";

// dev-01: static fixture only. Live sources (SSE) come in dev-02.
const events = scenario1 as unknown as AgentEvent[];

export default function Home() {
  return (
    <main>
      <h1>SME CI Agent</h1>
      <p className="muted">Run {events[0]?.run_id} (fixture, scenario 1)</p>
      <AnomalyTable events={events} />
      <Timeline events={events} />
    </main>
  );
}
