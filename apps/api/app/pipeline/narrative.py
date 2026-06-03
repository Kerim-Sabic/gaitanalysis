"""Report narrative generation.

Generates the clinician summary, patient-friendly explanation and review
recommendations **from the structured metrics only**. It is deterministic and
template-based by default (no external dependency, fully reproducible).

LLM SEAM
--------
``NarrativeGenerator`` is the single integration point for an LLM. To use one,
implement ``generate_with_llm`` and feed it ONLY the structured payload
(``build_llm_payload``). Guardrails enforced here regardless of backend:
  * never invents a measurement,
  * never names a disease / gives a diagnosis,
  * low confidence -> explicit "interpretation limited" wording,
  * always appends the non-diagnostic disclaimer.
"""
from __future__ import annotations

from app.pipeline.metrics import MetricsBundle
from app.schemas import AnalysisMode, QualityResult, TestType

DISCLAIMER = (
    "This analysis is intended to support clinical review and should not be used "
    "as a standalone diagnostic decision."
)

TEST_LABELS = {
    TestType.standard_walk: "standard walk test",
    TestType.timed_up_and_go: "Timed Up and Go test",
    TestType.six_minute_walk: "6-minute walk test",
    TestType.sit_to_stand: "sit-to-stand test",
    TestType.post_op_mobility: "post-operative mobility check",
    TestType.neuro_gait_screen: "neurological gait screen",
}


class NarrativeGenerator:
    def generate(
        self,
        bundle: MetricsBundle,
        quality: QualityResult,
        flags,
        test_type: TestType,
        analysis_mode: AnalysisMode,
    ) -> dict:
        m = {x.key: x for x in bundle.metrics}
        low_conf = bundle.overall_confidence < 0.5 or quality.overall_score < 55

        parts: list[str] = []
        test_label = TEST_LABELS.get(test_type, "gait assessment")
        if analysis_mode == AnalysisMode.demo:
            parts.append(
                "DEMO MODE — this summary is based on simulated/fallback keypoints "
                "and is not clinical-grade."
            )

        cad = m.get("cadence_steps_per_min")
        cyc = m.get("gait_cycles_detected")
        lead = f"AI-assisted gait quantification from a {test_label}"
        if cyc and cyc.value:
            lead += f" captured {int(cyc.value)} gait cycle(s)"
        if cad and cad.value:
            lead += f" at a cadence of {cad.value:.0f} steps/min"
        parts.append(lead + ".")

        review_flags = [f for f in flags if f.severity.value in ("low", "moderate", "high")]
        if review_flags:
            names = "; ".join(f.name.lower() for f in review_flags[:4])
            parts.append(f"Findings warranting review: {names}.")
        else:
            parts.append(
                "No specific gait pattern exceeded the configured screening thresholds."
            )

        parts.append(
            f"Mobility Risk Support Score: {bundle.risk_score:.0f}/100 "
            f"({bundle.risk_band.replace('_', ' ')}). This is a screening aid, not a "
            "fall-risk diagnosis."
        )

        if low_conf:
            parts.append(
                "Interpretation is limited by video quality and pose-confidence "
                "constraints; treat the quantitative values as approximate."
            )
        parts.append(
            "Findings should be reviewed by a clinician and interpreted alongside "
            "patient history and physical examination. " + DISCLAIMER
        )
        clinician_summary = " ".join(parts)

        # Patient-friendly version.
        patient = (
            "We used AI to measure how you walked in the video. It looked at your "
            "step timing, rhythm and joint movement. "
        )
        if review_flags:
            patient += (
                "A few things stood out that your clinician may want to look at more "
                "closely. "
            )
        else:
            patient += "Nothing specific stood out beyond our screening thresholds. "
        patient += (
            "This is a screening aid — your clinician will combine it with your history "
            "and an examination to decide what it means for you."
        )

        recommendations = self._recommendations(bundle, quality, flags, test_type)

        return {
            "report_summary": clinician_summary,
            "patient_summary": patient,
            "recommendations": recommendations,
        }

    def _recommendations(self, bundle, quality, flags, test_type) -> list[str]:
        recs: list[str] = []
        if quality.overall_score < 70:
            recs.append(
                "Repeat capture with improved video quality (see quality notes) to "
                "increase confidence before drawing conclusions."
            )
        if bundle.calibration_status == "uncalibrated":
            recs.append(
                "Record a known walking distance (or enter subject height) to enable "
                "calibrated speed and stride-length metrics."
            )
        if any(f.name.startswith("Marked") or f.severity.value == "moderate" for f in flags):
            recs.append(
                "Correlate the flagged asymmetry/pattern with clinical examination and "
                "relevant standardized scales."
            )
        recs.append(
            "Consider a follow-up capture to enable visit-over-visit trend comparison."
        )
        return recs

    # ------------------------------------------------------------------ #
    @staticmethod
    def build_llm_payload(bundle: MetricsBundle, quality: QualityResult, flags) -> dict:
        """Structured, measurement-only payload to hand to an LLM if enabled."""
        return {
            "metrics": [m.model_dump() for m in bundle.metrics],
            "asymmetry": [a.model_dump() for a in bundle.asymmetry],
            "quality": quality.model_dump(),
            "flags": [f.model_dump() for f in flags],
            "mobility_risk_support_score": bundle.risk_score,
            "overall_confidence": bundle.overall_confidence,
            "limitations": bundle.limitations,
        }

    def generate_with_llm(self, payload: dict) -> dict:  # pragma: no cover - seam
        """Override to call an LLM. Must obey the guardrails in the module docstring
        and must not introduce values absent from ``payload``."""
        raise NotImplementedError("Plug an LLM client in here; default uses templates.")
