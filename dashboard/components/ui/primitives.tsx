// Small shadcn-style primitives on Tailwind (no extra runtime). Variants follow the admin UI standard:
// solid = primary action, outline = secondary, danger = destructive.

import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "solid" | "outline" | "ghost" | "danger" | "ok";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  solid: "bg-accent text-accent-fg hover:brightness-110 shadow-sm",
  outline: "border border-border bg-surface text-fg hover:bg-surface-2",
  ghost: "text-muted hover:bg-surface-2 hover:text-fg",
  danger: "bg-bad text-white hover:brightness-110 shadow-sm",
  ok: "bg-ok text-white hover:brightness-110 shadow-sm",
};
const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-base gap-2",
  lg: "h-12 px-6 text-lg gap-2",
};

/** Button look for a Link (an <a> must not wrap a <button>). */
export function buttonClasses(variant: ButtonVariant = "solid", size: ButtonSize = "md", className?: string): string {
  return cn(
    "inline-flex select-none items-center justify-center rounded-lg font-semibold transition",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className,
  );
}

export function Button({
  variant = "solid",
  size = "md",
  className,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-lg font-semibold transition",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none disabled:hover:brightness-100",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...rest}
    />
  );
}

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border border-border bg-surface shadow-card", className)} {...rest} />;
}

/** Card header: short verb-like title ("Vì sao", "Làm gì") with an optional icon and right slot. */
export function CardTitle({ icon, children, right, className }: { icon?: ReactNode; children: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {icon && <span className="text-muted [&>svg]:size-5">{icon}</span>}
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{children}</h3>
      {right && <div className="ml-auto">{right}</div>}
    </div>
  );
}

export type Tone = "ok" | "bad" | "wait" | "run" | "accent" | "neutral";

const TONES: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok",
  bad: "bg-bad-soft text-bad",
  wait: "bg-wait-soft text-wait",
  run: "bg-run-soft text-run",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-surface-2 text-muted",
};

export function Badge({ tone = "neutral", className, ...rest }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-sm font-semibold whitespace-nowrap", TONES[tone], className)}
      {...rest}
    />
  );
}

export function toneText(tone: Tone): string {
  return { ok: "text-ok", bad: "text-bad", wait: "text-wait", run: "text-run", accent: "text-accent", neutral: "text-muted" }[tone];
}

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1.5 block text-sm font-semibold text-fg", className)} {...rest} />;
}

const FIELD =
  "w-full rounded-lg border border-border bg-surface px-3 text-base text-fg placeholder:text-muted/70 " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25 disabled:opacity-60";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(FIELD, "h-10", className)} {...rest} />;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(FIELD, "min-h-24 py-2 leading-relaxed", className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(FIELD, "h-10 cursor-pointer pr-8", className)} {...rest}>
      {children}
    </select>
  );
}

/** Confidence 0..1 as a bar; color follows the ask threshold idea: low = wait, high = ok. */
export function ConfidenceBar({ value, className, large }: { value: number | null; className?: string; large?: boolean }) {
  const v = value === null ? 0 : Math.max(0, Math.min(1, value));
  const tone = value === null ? "bg-run" : v >= 0.6 ? "bg-ok" : v >= 0.4 ? "bg-wait" : "bg-bad";
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        className={cn("relative flex-1 overflow-hidden rounded-full bg-surface-2", large ? "h-3" : "h-2")}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={v}
      >
        <div className={cn("h-full rounded-full transition-[width] duration-700", tone)} style={{ width: `${v * 100}%` }} />
      </div>
      <span className={cn("w-12 text-right font-semibold tabular-nums", large ? "text-lg" : "text-sm")}>
        {value === null ? "–" : `${Math.round(v * 100)}%`}
      </span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-shimmer rounded-lg bg-[linear-gradient(90deg,var(--surface-2)_0%,var(--border)_50%,var(--surface-2)_100%)] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}

export function EmptyState({ icon, children, action }: { icon?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center text-muted">
      {icon && <span className="rounded-full bg-surface-2 p-3 [&>svg]:size-6">{icon}</span>}
      <p>{children}</p>
      {action}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent", className)} aria-hidden />;
}
