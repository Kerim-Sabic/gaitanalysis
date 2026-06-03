import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ClinicalFlag } from "@horalix/shared";
import { Badge } from "@/components/ui/badge";
import { severityTone } from "@/lib/format";

export function FlagsList({ flags }: { flags: ClinicalFlag[] }) {
  return (
    <ul className="space-y-2.5">
      {flags.map((f, i) => {
        const tone = severityTone(f.severity);
        const Icon =
          f.severity === "info"
            ? f.name.startsWith("No specific")
              ? CheckCircle2
              : Info
            : AlertTriangle;
        return (
          <li
            key={i}
            className="flex gap-3 rounded-xl border border-border bg-surface-2/50 p-3"
          >
            <Icon
              className={
                tone === "good"
                  ? "mt-0.5 h-4 w-4 shrink-0 text-good"
                  : tone === "danger"
                    ? "mt-0.5 h-4 w-4 shrink-0 text-danger"
                    : tone === "warn"
                      ? "mt-0.5 h-4 w-4 shrink-0 text-warn"
                      : "mt-0.5 h-4 w-4 shrink-0 text-fg-subtle"
              }
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-fg">{f.name}</span>
                <Badge tone={tone}>{f.severity}</Badge>
                <span className="text-[10px] text-fg-subtle">
                  {Math.round(f.confidence * 100)}% conf
                </span>
              </div>
              <p className="mt-1 text-xs leading-snug text-fg-subtle">{f.explanation}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
