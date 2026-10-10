import { FileText } from "lucide-react";
import { diffLines, diffStats } from "@/lib/diff";
import { cn } from "@/lib/cn";
import { t } from "@/lib/strings";
import { Badge } from "@/components/ui/primitives";

/** "SOP cũ → mới": unified line diff, added lines green, removed lines red (FR-01.1, FR-01.2). */
export function SopDiff({
  sopId,
  fromVersion,
  toVersion,
  oldContent,
  newContent,
  fromLabel = t.proposal.sopCurrent,
  toLabel = t.proposal.sopNew,
}: {
  sopId: string;
  fromVersion: number | null;
  toVersion: number | null;
  oldContent: string | null;
  newContent: string;
  fromLabel?: string;
  toLabel?: string;
}) {
  const lines = diffLines(oldContent ?? "", newContent);
  const stats = diffStats(lines);
  const unchanged = oldContent !== null && !stats.changed;
  return (
    <div data-testid="sop-diff">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <FileText className="size-5 text-muted" />
        <span className="font-semibold" data-testid="sop-id">
          {sopId}
        </span>
        <span className="text-muted" data-testid="sop-versions">
          {fromLabel} {fromVersion !== null ? `v${fromVersion}` : ""} → {toLabel} {toVersion !== null ? `v${toVersion}` : ""}
        </span>
        <span className="ml-auto flex gap-1.5">
          {unchanged ? (
            <Badge tone="neutral" data-testid="sop-unchanged">
              {t.proposal.sopUnchanged}
            </Badge>
          ) : (
            <>
              {stats.added > 0 && <Badge tone="ok">{t.proposal.linesAdded(stats.added)}</Badge>}
              {stats.removed > 0 && <Badge tone="bad">{t.proposal.linesRemoved(stats.removed)}</Badge>}
            </>
          )}
        </span>
      </div>
      {oldContent === null && <p className="mb-2 text-sm text-muted">{t.proposal.sopNotAvailable}</p>}
      <ol className="overflow-hidden rounded-xl border border-border font-mono text-[0.9rem] leading-relaxed" data-testid="sop-lines">
        {lines.map((l, i) => (
          <li
            key={i}
            data-kind={l.kind}
            className={cn(
              "flex gap-3 px-3 py-1.5",
              l.kind === "add" && "bg-diff-add",
              l.kind === "del" && "bg-diff-del text-muted line-through decoration-bad/60",
              i > 0 && "border-t border-border/60",
            )}
          >
            <span
              className={cn("w-4 shrink-0 select-none text-center font-bold", l.kind === "add" ? "text-ok" : l.kind === "del" ? "text-bad" : "text-muted/50")}
              aria-hidden
            >
              {l.kind === "add" ? "+" : l.kind === "del" ? "−" : "·"}
            </span>
            <span className="whitespace-pre-wrap break-words">{l.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
