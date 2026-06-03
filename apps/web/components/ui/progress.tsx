import { cn } from "@/lib/utils";

export function Progress({
  value,
  className,
  tone = "primary",
}: {
  value: number; // 0..1
  className?: string;
  tone?: "primary" | "good" | "warn" | "danger";
}) {
  const toneClass = {
    primary: "bg-primary",
    good: "bg-good",
    warn: "bg-warn",
    danger: "bg-danger",
  }[tone];
  return (
    <div
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
    >
      <div
        className={cn("h-full rounded-full transition-all duration-500", toneClass)}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  );
}
