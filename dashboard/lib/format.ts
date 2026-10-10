// Display helpers. All of them accept unknown input and never return "null", "undefined" or "NaN" (NFR-6).

import { t } from "@/lib/strings";

export type Obj = Record<string, unknown>;

export const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);

export function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function str(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  return "";
}

const NUM = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });

/** 0.0619 -> "6,2%". Ratios only (unit "ratio" in the domain config). */
export function pct(v: unknown, digits = 1): string {
  const n = num(v);
  if (n === null) return t.common.none;
  return `${new Intl.NumberFormat("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n * 100)}%`;
}

export function fmtNum(v: unknown): string {
  const n = num(v);
  return n === null ? t.common.none : NUM.format(n);
}

/** Percentage points between two ratios, signed: -0.0422 -> "−4,2 điểm %". */
export function deltaPts(before: unknown, after: unknown): string {
  const b = num(before);
  const a = num(after);
  if (a === null || b === null) return "";
  const d = (a - b) * 100;
  const s = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(Math.abs(d));
  return `${d < 0 ? "−" : "+"}${s} điểm %`;
}

/** Local plant time (no zone in the data contract): "2026-03-10T22:00:00" -> "10/03/2026 22:00". */
export function dateTime(v: unknown): string {
  const s = str(v);
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(s);
  if (!m) return s || t.common.none;
  const date = `${m[3]}/${m[2]}/${m[1]}`;
  return m[4] ? `${date} ${m[4]}:${m[5]}` : date;
}

export function dateOnly(v: unknown): string {
  return dateTime(v).split(" ")[0];
}

/** Clock time of an event timestamp (UTC ISO from the backend), shown in the viewer's zone. */
export function clock(v: unknown): string {
  const d = new Date(str(v));
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Machine parameter name -> readable label; unit from the suffix (`_c` = °C). Unknown names stay as they are. */
export function paramLabel(name: unknown): { label: string; unit: string } {
  const s = str(name);
  const unit = s.endsWith("_c") ? "°C" : "";
  const zone = /^zone(\d+)_setpoint_c$/.exec(s);
  if (zone) return { label: `Nhiệt độ vùng ${zone[1]}`, unit };
  return { label: s, unit };
}

export function shiftLabel(v: unknown): string {
  const s = str(v);
  return ({ morning: "Ca sáng", afternoon: "Ca chiều", night: "Ca đêm" } as Record<string, string>)[s] ?? s;
}

export function groupLabel(v: unknown): string {
  const s = str(v);
  return t.groups[s] ?? s;
}

/** A hypothesis description may be a cause code (scripted LLM) or free text (real LLM). */
export function causeLabel(v: unknown): string {
  const s = str(v);
  return t.causes[s] ?? s;
}

export function kpiLabel(v: unknown): string {
  const s = str(v);
  return t.kpis[s] ?? s;
}

/** First line of an error, without a traceback. */
export function shortError(v: unknown): string {
  const s = str(v).trim();
  return s.split("\n")[0].slice(0, 240);
}
