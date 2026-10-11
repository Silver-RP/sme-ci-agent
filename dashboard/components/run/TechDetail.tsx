import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";
import { t } from "@/lib/strings";

/**
 * Raw backend text and codes (`wrong_setpoint`, `rollback_declined`, the English sentence the backend wrote, the
 * exception) folded away: the screen speaks plain Vietnamese, the original stays one click away for the team.
 * Hidden entirely in presentation mode.
 */
export function TechDetail({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <details className={cn("group text-sm text-muted present:hidden", className)} data-testid="tech-detail">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded font-medium transition hover:text-fg active:text-fg [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-4 transition group-open:rotate-90" />
        {t.common.techDetail}
      </summary>
      <div className="mt-2 rounded-lg bg-surface-2 p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">{children}</div>
    </details>
  );
}
