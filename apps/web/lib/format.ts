import type {
  FlagSeverity,
  MetricStatus,
  TestType,
} from "@horalix/shared";

export const TEST_TYPE_LABELS: Record<TestType, string> = {
  standard_walk: "Standard walk test",
  timed_up_and_go: "Timed Up and Go",
  six_minute_walk: "6-minute walk",
  sit_to_stand: "Sit-to-stand",
  post_op_mobility: "Post-op mobility check",
  neuro_gait_screen: "Neuro gait screen",
};

export const TEST_TYPE_DESCRIPTIONS: Record<TestType, string> = {
  standard_walk: "Patient walks across the camera view; cadence, timing, symmetry, joint ROM.",
  timed_up_and_go: "Stand, walk, turn, return, sit — phase timing and turn stability.",
  six_minute_walk: "Endurance walk; speed, cadence and fatigue trend (manual distance input).",
  sit_to_stand: "Repeated stands; rep timing, trunk angle and instability.",
  post_op_mobility: "Early post-operative mobility screen with cautious thresholds.",
  neuro_gait_screen: "Screen for neurological gait patterns (variability, asymmetry, festination).",
};

export const STATUS_LABELS: Record<MetricStatus, string> = {
  good: "Within expected range",
  review: "Review recommended",
  limited: "Limited",
  low_confidence: "Low confidence",
};

export function statusTone(status: MetricStatus): "good" | "warn" | "muted" | "danger" {
  switch (status) {
    case "good":
      return "good";
    case "review":
      return "warn";
    case "low_confidence":
      return "danger";
    default:
      return "muted";
  }
}

export function severityTone(sev: FlagSeverity): "good" | "warn" | "danger" | "muted" {
  switch (sev) {
    case "high":
      return "danger";
    case "moderate":
      return "warn";
    case "low":
      return "warn";
    default:
      return "muted";
  }
}

export function riskBandLabel(band: string): string {
  return (
    {
      low: "Low",
      review: "Review",
      elevated_review: "Elevated — review",
      insufficient_data: "Insufficient data",
    }[band] || band
  );
}

export function riskTone(band: string): "good" | "warn" | "danger" | "muted" {
  if (band === "low") return "good";
  if (band === "elevated_review") return "danger";
  if (band === "review") return "warn";
  return "muted";
}

export function fmt(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
  });
}

export function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

export function relativeDate(iso?: string | null): string {
  if (!iso) return "No analysis yet";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}
