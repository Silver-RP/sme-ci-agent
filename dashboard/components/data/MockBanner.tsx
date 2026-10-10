import { FlaskConical } from "lucide-react";
import { t } from "@/lib/strings";

export function MockBanner({ text = t.source.mockBanner }: { text?: string }) {
  return (
    <div className="mb-6 flex items-center gap-2 rounded-xl border border-dashed border-border bg-surface-2 px-4 py-2 text-sm text-muted" data-testid="mock-banner">
      <FlaskConical className="size-4 shrink-0" />
      {text}
    </div>
  );
}
