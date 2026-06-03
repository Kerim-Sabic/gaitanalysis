/**
 * Keypoint tracking-confidence color logic — mirrors
 * apps/api/app/pipeline/keypoint_quality.py thresholds.
 *
 * IMPORTANT: these colors describe TRACKING RELIABILITY, not disease. Red means
 * the keypoint (or a metric depending on it) is unreliable / needs review.
 */

export type QualityBand = "good" | "moderate" | "limited" | "unreliable";

export const CONFIDENCE_THRESHOLDS = {
  good: 0.8, // GREEN  — reliable tracking
  moderate: 0.6, // YELLOW — moderate confidence
  limited: 0.4, // ORANGE — low confidence / possible occlusion
  // < 0.4 -> RED (unreliable / missing)
} as const;

export const BAND_COLORS: Record<QualityBand, string> = {
  good: "#22c55e", // green
  moderate: "#eab308", // yellow
  limited: "#f97316", // orange
  unreliable: "#ef4444", // red
};

export const BAND_LABELS: Record<QualityBand, string> = {
  good: "Reliable tracking",
  moderate: "Moderate confidence",
  limited: "Low confidence / possible occlusion",
  unreliable: "Unreliable or missing",
};

export function confidenceBand(conf: number): QualityBand {
  if (conf >= CONFIDENCE_THRESHOLDS.good) return "good";
  if (conf >= CONFIDENCE_THRESHOLDS.moderate) return "moderate";
  if (conf >= CONFIDENCE_THRESHOLDS.limited) return "limited";
  return "unreliable";
}

export function confidenceColor(conf: number): string {
  return BAND_COLORS[confidenceBand(conf)];
}

export const KEYPOINT_LEGEND: { color: string; label: string }[] = [
  { color: BAND_COLORS.good, label: "Reliable tracking (≥ 0.80)" },
  { color: BAND_COLORS.moderate, label: "Moderate confidence (0.60–0.79)" },
  { color: BAND_COLORS.limited, label: "Low / possible occlusion (0.40–0.59)" },
  { color: BAND_COLORS.unreliable, label: "Unreliable or missing (< 0.40)" },
  { color: "#94a3b8", label: "Dashed ring = interpolated estimate" },
];

export const KEYPOINT_COLOR_DISCLAIMER =
  "The colored points show how confidently the AI could track each body part. " +
  "Green means reliable tracking. Yellow or orange means video angle, lighting, " +
  "clothing, motion blur, or foot visibility may have reduced confidence. Red means " +
  "that point or related metric should be reviewed carefully. These colors do not " +
  "diagnose disease.";
