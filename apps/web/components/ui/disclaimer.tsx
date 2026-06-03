import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export const DISCLAIMER_TEXT =
  "This analysis is intended to support clinical review and should not be used as a standalone diagnostic decision.";

export function DisclaimerBar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border border-border bg-surface-2/60 px-3 py-2 text-[11px] text-fg-subtle",
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" />
      <span>{DISCLAIMER_TEXT}</span>
    </div>
  );
}

export function DemoBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-warn/40 bg-warn/10 px-2.5 py-0.5 text-[11px] font-medium text-warn",
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-warn" />
      Demo mode — simulated / fallback analysis. Not clinical-grade.
    </span>
  );
}
