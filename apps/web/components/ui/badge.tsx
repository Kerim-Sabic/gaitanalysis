import * as React from "react";
import { cn } from "@/lib/utils";

type Tone = "good" | "warn" | "danger" | "muted" | "primary";

const tones: Record<Tone, string> = {
  good: "bg-good/15 text-good border-good/30",
  warn: "bg-warn/15 text-warn border-warn/30",
  danger: "bg-danger/15 text-danger border-danger/30",
  muted: "bg-muted text-fg-subtle border-border",
  primary: "bg-primary/15 text-primary border-primary/30",
};

export function Badge({
  tone = "muted",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
