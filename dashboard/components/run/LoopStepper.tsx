import { Check, RotateCcw } from "lucide-react";
import { cn } from "@/lib/cn";
import { MAIN_STEPS, type StepKey, type StepState } from "@/lib/runModel";
import { t } from "@/lib/strings";

/** The 8-step loop always on top (FR-08). The current step glows; rollback appears as a branch once it happens. */
export function LoopStepper({ states, showRollback }: { states: Record<StepKey, StepState>; showRollback: boolean }) {
  return (
    <nav aria-label="Vòng cải tiến" className="rounded-xl border border-border bg-surface p-3 shadow-card" data-testid="loop-stepper">
      <ol className="flex items-stretch gap-1 overflow-x-auto">
        {MAIN_STEPS.map((s, i) => (
          <Step key={s} step={s} index={i + 1} state={states[s]} last={i === MAIN_STEPS.length - 1} />
        ))}
        {showRollback && (
          <li
            className={cn(
              "ml-2 flex shrink-0 items-center gap-2 rounded-xl border border-dashed px-3 py-2",
              states.rollback === "active" ? "border-bad bg-bad-soft text-bad" : "border-border text-muted",
            )}
            data-step="rollback"
            data-state={states.rollback}
          >
            <RotateCcw className="size-5" />
            <span className="font-semibold">{t.steps.rollback}</span>
          </li>
        )}
      </ol>
    </nav>
  );
}

function Step({ step, index, state, last }: { step: StepKey; index: number; state: StepState; last: boolean }) {
  return (
    // below lg only the active step keeps its name, so the whole loop fits one row without hidden scrolling
    <li
      className={cn("flex items-center lg:min-w-30 lg:flex-1", state === "active" && "flex-1")}
      title={t.steps[step]}
      data-step={step}
      data-state={state}
    >
      <div
        className={cn(
          "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 transition-colors duration-500",
          state === "active" && "bg-accent-soft",
        )}
      >
        <span
          className={cn(
            "grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold transition-colors duration-500",
            state === "done" && "bg-ok text-white",
            state === "active" && "animate-pulse-ring bg-accent text-accent-fg",
            state === "todo" && "bg-surface-2 text-muted",
          )}
        >
          {state === "done" ? <Check className="size-4" strokeWidth={3} /> : index}
        </span>
        <span className={cn("min-w-0 leading-tight", state !== "active" && "hidden lg:block")}>
          <span className={cn("block whitespace-nowrap text-sm font-semibold", state === "todo" && "text-muted", state === "active" && "text-accent")}>{t.steps[step]}</span>
          <span className="hidden truncate text-xs text-muted 2xl:block">{t.stepHints[step]}</span>
        </span>
      </div>
      {!last && <span className={cn("mx-1 h-0.5 w-4 shrink-0 rounded", state === "done" ? "bg-ok" : "bg-border")} aria-hidden />}
    </li>
  );
}
