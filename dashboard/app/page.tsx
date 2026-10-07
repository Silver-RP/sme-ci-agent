"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { LiveRun } from "@/components/LiveRun";
import { RunView } from "@/components/RunView";
import { createFixtureSource, createSseSource } from "@/lib/sources";
import scenario1 from "@/fixtures/scenario1.json";

// ?source=live starts/follows a run on the real backend. ?source=fixture (default) replays the fixture; ?source=sse&run=<id> reads GET /runs/{id}/events.
function Home() {
  const params = useSearchParams();
  const source = params.get("source") ?? "fixture";
  const run = params.get("run") ?? "";
  if (source === "live") return <LiveRun />;
  if (source === "sse" && run) {
    return (
      <RunView
        title={`Run ${run} (live SSE)`}
        sourceKey={`sse:${run}`}
        makeSource={() => createSseSource(run)}
      />
    );
  }
  return (
    <RunView
      title="Run run_seed42 (fixture replay, scenario 1)"
      sourceKey="fixture"
      makeSource={() => createFixtureSource(scenario1 as unknown[], { intervalMs: 300 })}
    />
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p>Loading...</p>}>
      <Home />
    </Suspense>
  );
}
