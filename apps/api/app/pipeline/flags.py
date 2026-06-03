"""Clinical flag generation.

Flags are cautious, pattern-level observations for clinician review — never
diagnoses. Each flag cites the supporting metric(s) and carries its own
confidence. Poor video quality raises a dedicated "interpretation limited" flag
rather than silently degrading other flags.
"""
from __future__ import annotations

from app.pipeline.metrics import MetricsBundle
from app.schemas import ClinicalFlag, FlagSeverity, MetricStatus, QualityResult


class ClinicalFlagService:
    def generate(self, bundle: MetricsBundle, quality: QualityResult) -> list[ClinicalFlag]:
        flags: list[ClinicalFlag] = []

        def metric(key):
            return next((m for m in bundle.metrics if m.key == key), None)

        def asym(key):
            return next((a for a in bundle.asymmetry if a.key == key), None)

        # Quality gate first.
        if quality.overall_score < 55:
            flags.append(ClinicalFlag(
                name="Interpretation limited by video quality",
                severity=FlagSeverity.moderate,
                confidence=0.9,
                explanation=(
                    "Video quality and/or pose confidence constraints reduce the "
                    "reliability of the quantitative findings below."
                ),
                supporting_metrics=["video_quality"],
            ))

        # Temporal asymmetry.
        step_asym = asym("step_time_asymmetry")
        if step_asym and step_asym.asymmetry_percent is not None:
            pct = step_asym.asymmetry_percent
            if pct >= 18:
                sev, label = FlagSeverity.moderate, "Marked temporal step asymmetry"
            elif pct >= 10:
                sev, label = FlagSeverity.low, "Moderate temporal step asymmetry"
            elif pct >= 6:
                sev, label = FlagSeverity.low, "Mild temporal step asymmetry"
            else:
                sev, label = None, None
            if sev:
                flags.append(ClinicalFlag(
                    name=label, severity=sev, confidence=round(step_asym.confidence, 2),
                    explanation=(
                        f"Left/right step timing differs by {pct:.1f}%. Asymmetric "
                        "timing can accompany antalgic, neurological or post-operative "
                        "gait patterns and warrants clinical correlation."
                    ),
                    supporting_metrics=["left_step_time_sec", "right_step_time_sec"],
                ))

        # Reduced cadence.
        cad = metric("cadence_steps_per_min")
        if cad and cad.value is not None and cad.value < 90:
            flags.append(ClinicalFlag(
                name="Reduced cadence",
                severity=FlagSeverity.low if cad.value > 75 else FlagSeverity.moderate,
                confidence=round(cad.confidence, 2),
                explanation=(
                    f"Cadence ({cad.value:.0f} steps/min) is below the typical "
                    "comfortable-pace range; consider pace, pain, or fatigue."
                ),
                supporting_metrics=["cadence_steps_per_min"],
            ))

        # Reduced knee flexion (possible stiff-knee / shuffling pattern).
        for side in ("left", "right"):
            m = metric(f"knee_rom_{side}_deg")
            if m and m.value is not None and m.value < 40:
                flags.append(ClinicalFlag(
                    name=f"Reduced knee flexion ({side})",
                    severity=FlagSeverity.low,
                    confidence=round(m.confidence, 2),
                    explanation=(
                        f"{side.capitalize()} knee sagittal excursion ({m.value:.0f}°) is "
                        "lower than typical; may reflect a stiff-knee or shuffling pattern."
                    ),
                    supporting_metrics=[f"knee_rom_{side}_deg"],
                ))

        # Variability / instability.
        var = metric("stride_time_variability")
        if var and var.value is not None and var.value > 8:
            flags.append(ClinicalFlag(
                name="Increased gait variability",
                severity=FlagSeverity.low if var.value < 14 else FlagSeverity.moderate,
                confidence=round(var.confidence, 2),
                explanation=(
                    f"Stride-time variability ({var.value:.0f}% CV) is elevated; higher "
                    "variability has been associated with reduced gait stability."
                ),
                supporting_metrics=["stride_time_variability"],
            ))
        sway = metric("trunk_sway_index")
        if sway and sway.value is not None and sway.value > 6:
            flags.append(ClinicalFlag(
                name="Lateral/trunk instability pattern",
                severity=FlagSeverity.low,
                confidence=round(sway.confidence, 2),
                explanation=(
                    "Elevated trunk angular variability may indicate balance or "
                    "stability challenges; correlate with balance assessment."
                ),
                supporting_metrics=["trunk_sway_index"],
            ))

        # Slow walking speed.
        spd = metric("walking_speed_m_per_s")
        if spd and spd.value is not None and spd.value < 0.8:
            flags.append(ClinicalFlag(
                name="Reduced walking speed (mobility-relevant range)",
                severity=FlagSeverity.low,
                confidence=round(spd.confidence, 2),
                explanation=(
                    f"Estimated speed ({spd.value:.2f} m/s) falls in a range often "
                    "considered mobility-relevant. Confirm with a calibrated distance."
                ),
                supporting_metrics=["walking_speed_m_per_s"],
            ))

        # Composite mobility-risk-support summary flag.
        if bundle.risk_band == "elevated_review":
            flags.append(ClinicalFlag(
                name="Multiple mobility indicators warrant review",
                severity=FlagSeverity.moderate,
                confidence=round(bundle.overall_confidence, 2),
                explanation=(
                    "Several measured aspects (asymmetry, pace, variability, stability) "
                    "combine into an elevated Mobility Risk Support Score. This is a "
                    "screening signal for clinician review, not a fall-risk diagnosis."
                ),
                supporting_metrics=["mobility_risk_support_score"],
            ))

        if not flags:
            flags.append(ClinicalFlag(
                name="No specific pattern flagged",
                severity=FlagSeverity.info,
                confidence=round(bundle.overall_confidence, 2),
                explanation=(
                    "Measured parameters fell within the configured screening "
                    "thresholds. Absence of a flag is not confirmation of normal gait."
                ),
                supporting_metrics=[],
            ))
        return flags

    @staticmethod
    def _quality_status(quality: QualityResult) -> MetricStatus:
        if quality.overall_score >= 75:
            return MetricStatus.good
        if quality.overall_score >= 55:
            return MetricStatus.review
        return MetricStatus.limited
