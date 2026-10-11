"use client";

// shadcn/ui Tooltip (Radix) on the dashboard's tokens. Used where a control shows only an icon.

import type { ComponentProps, ReactNode } from "react";
import { Tooltip as TooltipPrimitive } from "radix-ui";
import { cn } from "@/lib/cn";

/** Each tooltip brings its own provider (as current shadcn does), so any component can use it without app setup. */
export function Tooltip({
  content,
  children,
  side = "right",
  disabled,
  className,
}: {
  content: ReactNode;
  children: ReactNode;
  side?: ComponentProps<typeof TooltipPrimitive.Content>["side"];
  /** render the child alone, e.g. when its label is already visible next to the icon */
  disabled?: boolean;
  className?: string;
}) {
  if (disabled) return <>{children}</>;
  return (
    <TooltipPrimitive.Provider delayDuration={200}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={8}
            className={cn("z-50 rounded-md bg-fg px-2.5 py-1.5 text-xs font-medium text-bg shadow-card data-[state=delayed-open]:animate-fade-up", className)}
          >
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
