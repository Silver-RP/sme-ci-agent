"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BookOpenCheck, ChartLine, History, Maximize2, Menu, Minimize2, Moon, PlayCircle, ScrollText, Sun, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { t } from "@/lib/strings";

type NavItem = { href: string; label: string; icon: LucideIcon };

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: t.nav.sectionRun,
    items: [
      { href: "/", label: t.nav.run, icon: PlayCircle },
      { href: "/runs", label: t.nav.runs, icon: History },
    ],
  },
  {
    section: t.nav.sectionData,
    items: [
      { href: "/overview", label: t.nav.overview, icon: ChartLine },
      { href: "/kaizen", label: t.nav.kaizen, icon: BookOpenCheck },
      { href: "/audit", label: t.nav.audit, icon: ScrollText },
    ],
  },
];

function readPref(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function writePref(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode: the preference just isn't remembered */
  }
}

function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-9 place-items-center rounded-xl bg-accent text-accent-fg shadow-sm">
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" aria-hidden>
          <path d="M4 12a8 8 0 0 1 13.7-5.6M20 12a8 8 0 0 1-13.7 5.6" />
          <path d="M18 3v4h-4M6 21v-4h4" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-tight">
          <div className="font-bold tracking-tight">{t.app.name}</div>
          <div className="text-xs text-muted">{t.app.tagline}</div>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [present, setPresent] = useState(false);
  const [dark, setDark] = useState(false);
  const [open, setOpen] = useState(false);

  // restore preferences after mount (no SSR mismatch)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of a browser-only preference
    setDark(readPref("sme.theme") === "dark");
    setPresent(readPref("sme.present") === "true");
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  useEffect(() => {
    document.documentElement.dataset.present = String(present);
  }, [present]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (e.key === "f" || e.key === "F") {
        setPresent((p) => {
          writePref("sme.present", String(!p));
          return !p;
        });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const current = NAV.flatMap((g) => g.items).find((i) => (i.href === "/" ? pathname === "/" : pathname.startsWith(i.href)));

  const togglePresent = () => {
    writePref("sme.present", String(!present));
    setPresent(!present);
  };
  const toggleDark = () => {
    writePref("sme.theme", dark ? "light" : "dark");
    setDark(!dark);
  };

  const sidebar = (
    <nav aria-label="Điều hướng chính" className="flex h-full flex-col gap-6 p-4">
      <Logo />
      {NAV.map((g) => (
        <div key={g.section}>
          <div className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted">{g.section}</div>
          <ul className="space-y-1">
            {g.items.map((item) => {
              const active = item === current;
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex items-center gap-3 rounded-lg px-3 py-2 text-[0.95rem] font-medium transition",
                      active ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2 hover:text-fg",
                    )}
                  >
                    {active && <span className="absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-accent" />}
                    <Icon className="size-5" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <div className="mt-auto rounded-xl border border-dashed border-border p-3 text-xs text-muted">{t.app.sandbox}</div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      {!present && (
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-border bg-surface lg:block">{sidebar}</aside>
      )}
      {open && !present && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 bg-black/40" aria-label={t.common.close} onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r border-border bg-surface">
            <button className="absolute right-3 top-4 rounded-lg p-1 text-muted hover:bg-surface-2" onClick={() => setOpen(false)} aria-label={t.common.close}>
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-surface/85 px-4 backdrop-blur md:px-6">
          {!present && (
            <button className="rounded-lg p-2 text-muted hover:bg-surface-2 lg:hidden" onClick={() => setOpen(true)} aria-label={t.topbar.menu}>
              <Menu className="size-5" />
            </button>
          )}
          {present ? (
            <Logo />
          ) : (
            <div className="flex min-w-0 items-center gap-2 text-sm">
              <span className="text-muted">{t.app.name}</span>
              <span className="text-muted">/</span>
              <span className="truncate font-semibold">{current?.label ?? ""}</span>
            </div>
          )}
          <div className="ml-auto flex items-center gap-1.5">
            <button
              onClick={toggleDark}
              className="rounded-lg p-2 text-muted transition hover:bg-surface-2 hover:text-fg"
              aria-label={dark ? t.topbar.themeLight : t.topbar.themeDark}
              title={dark ? t.topbar.themeLight : t.topbar.themeDark}
            >
              {dark ? <Sun className="size-5" /> : <Moon className="size-5" />}
            </button>
            <button
              onClick={togglePresent}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-semibold transition",
                present ? "bg-accent text-accent-fg" : "text-muted hover:bg-surface-2 hover:text-fg",
              )}
              title={t.topbar.presentHint}
              data-testid="present-toggle"
            >
              {present ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
              <span className="hidden sm:inline">{present ? t.topbar.exitPresent : t.topbar.present}</span>
            </button>
            {!present && (
              <div className="ml-2 hidden items-center gap-2 border-l border-border pl-3 md:flex">
                <div className="grid size-8 place-items-center rounded-full bg-accent-soft text-sm font-bold text-accent">QA</div>
                <div className="text-xs leading-tight text-muted">{t.topbar.role}</div>
              </div>
            )}
          </div>
        </header>
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}

export function PageHeader({ title, lead, right }: { title: string; lead?: string; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-4">
      <div className="min-w-0 flex-1">
        <h1 className="text-[1.75rem] font-semibold tracking-tight">{title}</h1>
        {lead && <p className="mt-1 max-w-3xl text-muted">{lead}</p>}
      </div>
      {right}
    </div>
  );
}

export function PageBody({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return <main className={cn("mx-auto w-full px-4 py-6 md:px-8", wide ? "max-w-[1800px]" : "max-w-6xl")}>{children}</main>;
}
