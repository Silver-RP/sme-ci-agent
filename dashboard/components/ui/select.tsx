"use client";

// shadcn/ui Select (Radix) on the dashboard's own tokens, instead of the native <select> whose open list the
// browser draws (unstyled, different on every OS, ignores the dark theme).

import type { ComponentProps } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Select as SelectPrimitive } from "radix-ui";
import { cn } from "@/lib/cn";

export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;

export function SelectTrigger({ className, children, size = "md", ...rest }: ComponentProps<typeof SelectPrimitive.Trigger> & { size?: "sm" | "md" }) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 text-left text-fg transition",
        "hover:bg-surface-2 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25 active:bg-surface-2",
        "disabled:cursor-not-allowed disabled:opacity-60 data-placeholder:text-muted",
        // the value is a single line: long labels end with "…" instead of growing the trigger
        "[&>span]:min-w-0 [&>span]:truncate",
        // same height and text as Input; 16px on phones so iOS does not zoom
        size === "sm" ? "h-8 text-sm" : "h-9 text-base md:text-sm",
        className,
      )}
      {...rest}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="size-4 shrink-0 text-muted" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({ className, children, position = "popper", ...rest }: ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position={position}
        sideOffset={4}
        className={cn(
          "z-50 max-h-(--radix-select-content-available-height) min-w-(--radix-select-trigger-width) overflow-hidden rounded-lg border border-border bg-surface text-fg shadow-card",
          "data-[state=open]:animate-fade-up",
          className,
        )}
        {...rest}
      >
        <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectItem({ className, children, ...rest }: ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "relative flex cursor-pointer select-none items-center rounded-md py-2 pl-8 pr-3 text-sm outline-none transition",
        "data-highlighted:bg-surface-2 data-[state=checked]:font-semibold data-[state=checked]:text-accent active:bg-accent-soft",
        "data-disabled:pointer-events-none data-disabled:opacity-50",
        className,
      )}
      {...rest}
    >
      <span className="absolute left-2 grid size-4 place-items-center">
        <SelectPrimitive.ItemIndicator>
          <Check className="size-4" />
        </SelectPrimitive.ItemIndicator>
      </span>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}
