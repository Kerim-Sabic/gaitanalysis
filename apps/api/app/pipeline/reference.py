"""Reference ranges and interpretation banding.

These are population-level orientation values drawn from general gait literature
for healthy adults. They are NOT diagnostic thresholds — they only shape cautious
wording ("within expected range" / "mild" / "moderate"). All numbers should be
revisited against the cohort and validated per docs/validation_plan.md.
"""
from __future__ import annotations

from app.schemas import MetricStatus

# Healthy-adult orientation ranges (context dependent: age, height, footwear).
REFERENCE = {
    "cadence_steps_per_min": (95.0, 125.0, "≈ 95–125 steps/min (healthy adult, comfortable pace)"),
    "walking_speed_m_per_s": (1.0, 1.4, "≈ 1.0–1.4 m/s comfortable; <0.8 m/s often clinically relevant"),
    "knee_rom_deg": (50.0, 70.0, "≈ 55–65° sagittal knee excursion in swing"),
    "hip_rom_deg": (30.0, 50.0, "≈ 35–45° sagittal hip excursion"),
    "step_time_sec": (0.45, 0.65, "≈ 0.5–0.6 s per step at comfortable pace"),
    "stance_pct": (58.0, 65.0, "≈ 60–62% of the gait cycle is stance"),
}

# Asymmetry banding (% difference between sides).
ASYMMETRY_BANDS = [
    (5.0, MetricStatus.good, "Within expected symmetry."),
    (10.0, MetricStatus.review, "Mild asymmetry — clinician review recommended."),
    (18.0, MetricStatus.review, "Moderate asymmetry — clinician review recommended."),
    (float("inf"), MetricStatus.review, "Marked asymmetry — interpret with caution and review."),
]


def asymmetry_status(pct: float | None) -> tuple[MetricStatus, str]:
    if pct is None:
        return MetricStatus.limited, "Could not be computed reliably."
    for threshold, status, text in ASYMMETRY_BANDS:
        if pct <= threshold:
            return status, text
    return MetricStatus.review, "Interpret with caution."


def in_range_status(value: float | None, key: str) -> tuple[MetricStatus, str]:
    if value is None or key not in REFERENCE:
        return MetricStatus.limited, ""
    lo, hi, _ = REFERENCE[key]
    if lo <= value <= hi:
        return MetricStatus.good, "Within expected range (context dependent)."
    if value < lo:
        return MetricStatus.review, "Below the typical range — clinician review recommended."
    return MetricStatus.review, "Above the typical range — clinician review recommended."


def reference_text(key: str) -> str | None:
    entry = REFERENCE.get(key)
    return entry[2] if entry else None
