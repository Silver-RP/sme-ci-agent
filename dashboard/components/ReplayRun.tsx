"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FastForward, Pause, Play, RotateCcw, Wand2 } from "lucide-react";
import { RunScreen } from "@/components/run/RunScreen";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import type { RunActions } from "@/components/run/types";
import type { RunStatus } from "@/lib/api";
import { cn } from "@/lib/cn";
import { str } from "@/lib/format";
import { findRecording, RECORDINGS, REPLAY_APPROVERS } from "@/lib/recordings";
import { chunksOf, nextHint, visibleEvents } from "@/lib/replay";
import { t } from "@/lib/strings";

const STEP_MS = 650;
const AUTO_WAIT_MS = 3500;

/**
 * Replays a recorded run with the same screens as live (FR-07). Events appear one by one; at each
 * question / approval / error the replay waits for the presenter (or advances by itself in Auto mode).
 * The buttons only move the recording forward: it always follows the recorded branch.
 */
export function ReplayRun({
  file,
  intervalMs = STEP_MS,
  toolbar: extra,
}: {
  file?: string | null;
  intervalMs?: number;
  toolbar?: React.ReactNode;
}) {
  const router = useRouter();
  const recording = findRecording(file);
  const chunks = useMemo(() => chunksOf(recording), [recording]);
  const [chunk, setChunk] = useState(0);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [auto, setAuto] = useState(false);
  const [pastError, setPastError] = useState<string | null>(null);

  const current = chunks[chunk];
  const emitting = current !== undefined && cursor < current.events.length;
  const waiting = !emitting && current?.next !== null && current?.next !== undefined;

  // reset when the recording changes
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- restart the replay for a new recording */
    setChunk(0);
    setCursor(0);
    setPastError(null);
    setPlaying(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [recording]);

  useEffect(() => {
    if (!playing || !emitting) return;
    const id = setTimeout(() => setCursor((c) => c + 1), intervalMs / speed);
    return () => clearTimeout(id);
  }, [playing, emitting, cursor, speed, intervalMs]);

  const advance = () => {
    if (!current?.next) return;
    if (current.status?.state === "error") setPastError(str(current.status.error));
    setChunk((c) => Math.min(c + 1, chunks.length - 1));
    setCursor(0);
  };

  // Space pauses / resumes, like a video player; ignored while typing or when a control has focus
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.key !== " " || (target && ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(target.tagName))) return;
      e.preventDefault();
      setPlaying((p) => !p);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!auto || !waiting || !playing) return;
    const id = setTimeout(advance, AUTO_WAIT_MS / speed);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, waiting, playing, chunk, speed]);

  const events = visibleEvents(chunks, chunk, cursor);
  const runId = events[0]?.run_id ?? current?.status?.run_id ?? null;
  const status: RunStatus | null = emitting
    ? { run_id: runId ?? "", state: "running", status: "", pending: null }
    : (current?.status ?? null);

  const actions: RunActions = {
    answer: advance,
    decide: advance,
    retry: advance,
  };

  const restart = () => {
    setChunk(0);
    setCursor(0);
    setPastError(null);
    setPlaying(true);
  };

  const hint = waiting ? nextHint(current?.next ?? null) : "";

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2" data-testid="replay-controls">
      {extra}
      <Select value={recording.name} onValueChange={(name) => router.push(`/?source=fixture&file=${encodeURIComponent(name)}`)}>
        <SelectTrigger size="sm" className="w-80" aria-label={t.replay.file} data-testid="replay-file">
          <SelectValue />
        </SelectTrigger>
        <SelectContent align="end">
          {RECORDINGS.map((r) => (
            <SelectItem key={r.name} value={r.name}>
              {t.replay.files[r.name] ?? r.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <ToolButton
        onClick={() => setPlaying(!playing)}
        label={`${playing ? t.replay.pause : t.replay.play} (Space)`}
        text={playing ? t.replay.pause : t.replay.play}
        testId="replay-play"
      >
        {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
      </ToolButton>
      <ToolButton onClick={() => setSpeed(speed === 1 ? 2 : 1)} label={t.replay.speedHint} active={speed === 2} testId="replay-speed">
        <FastForward className="size-4" />
        <span className="text-xs font-bold">{speed}×</span>
      </ToolButton>
      <ToolButton onClick={() => setAuto(!auto)} label={t.replay.autoHint} text={t.replay.auto} active={auto} testId="replay-auto">
        <Wand2 className="size-4" />
      </ToolButton>
      <ToolButton onClick={restart} label={t.replay.restart} testId="replay-restart">
        <RotateCcw className="size-4" />
      </ToolButton>
    </div>
  );

  return (
    <>
      <RunScreen
        mode="replay"
        runId={runId}
        events={events}
        connection={emitting ? "open" : "closed"}
        status={status}
        busy={emitting}
        started
        pastError={pastError}
        approvers={REPLAY_APPROVERS}
        actions={actions}
        toolbar={toolbar}
        notice={hint}
        defaultApprover={str(current?.next?.body?.decided_by) || undefined}
      />
    </>
  );
}

/** Presenter control: icon (+ short word on wide screens), the full meaning in a tooltip. */
function ToolButton({
  children,
  onClick,
  label,
  text,
  active,
  testId,
}: {
  children: React.ReactNode;
  onClick: () => void;
  label: string;
  /** visible word next to the icon from xl; the icon alone was ambiguous (Auto, 2×, ⟲) */
  text?: string;
  active?: boolean;
  testId?: string;
}) {
  return (
    <Tooltip content={label} side="bottom">
      <button
        type="button"
        onClick={onClick}
        aria-label={label}
        aria-pressed={active}
        data-testid={testId}
        className={cn(
          "flex h-9 items-center gap-1.5 rounded-lg border px-2.5 text-sm font-medium transition active:scale-[0.97]",
          active ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-muted hover:text-fg active:bg-surface-2",
        )}
      >
        {children}
        {text && <span className="hidden xl:inline">{text}</span>}
      </button>
    </Tooltip>
  );
}
