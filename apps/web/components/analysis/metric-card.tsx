import type { Metric } from "@horalix/shared";
import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS, fmt, pct, statusTone } from "@/lib/format";
import { cn } from "@/lib/utils";

export function MetricCard({ metric }: { metric: Metric }) {
  const tone = statusTone(metric.status);
  return (
    <div className="group rounded-2xl border border-border bg-surface p-4 shadow-soft transition hover:border-primary/30">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-fg-subtle">{metric.label}</span>
        <Badge tone={tone}>{STATUS_LABELS[metric.status]}</Badge>
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="tabular text-2xl font-semibold tracking-tight text-fg">
          {fmt(metric.value, 2)}
        </span>
        <span className="text-xs text-fg-subtle">{metric.unit}</span>
      </div>
      {metric.interpretation ? (
        <p className="mt-1.5 line-clamp-2 text-[11px] leading-snug text-fg-subtle">
          {metric.interpretation}
        </p>
      ) : null}
      <div className="mt-3 flex items-center justify-between text-[10px] text-fg-subtle/80">
        <span>Confidence {pct(metric.confidence)}</span>
        <div className="h-1 w-16 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full",
              tone === "good" ? "bg-good" : tone === "danger" ? "bg-danger" : "bg-primary",
            )}
            style={{ width: `${Math.round(metric.confidence * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  unit,
  tone = "muted",
  sub,
}: {
  label: string;
  value: string;
  unit?: string;
  tone?: "good" | "warn" | "danger" | "muted" | "primary";
  sub?: string;
}) {
  const ring = {
    good: "ring-good/20",
    warn: "ring-warn/20",
    danger: "ring-danger/20",
    primary: "ring-primary/20",
    muted: "ring-border",
  }[tone];
  return (
    <div className={cn("rounded-2xl border border-border bg-surface p-4 shadow-soft ring-1", ring)}>
      <span className="text-xs font-medium text-fg-subtle">{label}</span>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="tabular text-2xl font-semibold tracking-tight">{value}</span>
        {unit ? <span className="text-xs text-fg-subtle">{unit}</span> : null}
      </div>
      {sub ? <p className="mt-1 text-[11px] text-fg-subtle">{sub}</p> : null}
    </div>
  );
}
