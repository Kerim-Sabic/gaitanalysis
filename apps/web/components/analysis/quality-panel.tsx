import type { QualityResult } from "@horalix/shared";
import { cn } from "@/lib/utils";

const ITEMS: { key: keyof QualityResult; label: string }[] = [
  { key: "lighting_score", label: "Lighting" },
  { key: "blur_score", label: "Sharpness" },
  { key: "resolution_score", label: "Resolution" },
  { key: "camera_stability", label: "Camera stability" },
  { key: "full_body_visibility", label: "Full body visible" },
  { key: "feet_visibility", label: "Feet visible" },
];

function tone(v: number) {
  if (v >= 75) return "bg-good";
  if (v >= 55) return "bg-warn";
  return "bg-danger";
}

export function QualityPanel({ quality }: { quality: QualityResult }) {
  return (
    <div className="space-y-3">
      {ITEMS.map(({ key, label }) => {
        const v = Number(quality[key] ?? 0);
        return (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-fg-subtle">{label}</span>
              <span className="tabular font-medium">{Math.round(v)}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full transition-all", tone(v))} style={{ width: `${v}%` }} />
            </div>
          </div>
        );
      })}
      {quality.warnings.length ? (
        <ul className="mt-3 space-y-1 text-[11px] text-warn">
          {quality.warnings.map((w, i) => (
            <li key={i}>• {w}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
