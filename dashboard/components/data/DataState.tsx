import type { ReactNode } from "react";
import { CloudOff, RefreshCw } from "lucide-react";
import { Button, Card, Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { t } from "@/lib/strings";
import type { ApiState } from "@/lib/useApi";

/** Loading skeleton, or the backend error with a Retry, or the data. Old data stays on screen while reloading. */
export function DataState<T>({ state, skeleton, children }: { state: ApiState<T>; skeleton?: ReactNode; children: (data: NonNullable<T>) => ReactNode }) {
  if (state.error) {
    return (
      <Card className="flex flex-col items-center gap-3 p-8 text-center" role="alert" data-testid="data-error">
        <span className="rounded-full bg-bad-soft p-3 text-bad">
          <CloudOff className="size-6" />
        </span>
        <p className="text-lg font-semibold">{t.data.failed}</p>
        <p className="text-sm text-muted">
          <code>{state.error}</code>
        </p>
        <p className="text-sm text-muted">{t.data.hint}</p>
        <Button variant="outline" onClick={state.reload}>
          <RefreshCw className="size-4" />
          {t.data.retry}
        </Button>
      </Card>
    );
  }
  if (state.data === null || state.data === undefined) {
    return (
      <div className="space-y-3" aria-busy="true" data-testid="data-loading">
        {skeleton ?? [0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
      </div>
    );
  }
  return <>{children(state.data as NonNullable<T>)}</>;
}

/** Header button: the screens do not poll, the presenter refreshes after a run moves on. */
export function RefreshButton({ state }: { state: Pick<ApiState<unknown>, "loading" | "reload"> }) {
  return (
    <Button variant="outline" size="sm" onClick={state.reload} disabled={state.loading}>
      <RefreshCw className={cn("size-4", state.loading && "animate-spin")} />
      {t.data.refresh}
    </Button>
  );
}
