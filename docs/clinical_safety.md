# Clinical Safety & Intended Use

> **Horalix Gait AI provides AI-assisted gait quantification to support clinical
> review. It is not a diagnostic device and must not be used as a standalone
> diagnostic decision.** This document describes intended use, limitations and
> known failure modes. It is a starting framework, not a regulatory submission.

## Intended use

- **What it is:** a markerless, single-camera tool that quantifies gait
  parameters (cadence, step/stride timing, stance/swing, joint ROM, left–right
  asymmetry, variability, trunk sway) and produces a structured, clinician-
  readable report with explicit confidence and limitations.
- **Intended users:** physiotherapists, neurologists, orthopedic clinicians,
  rehabilitation and elderly-care teams, and researchers — i.e. trained
  professionals who interpret the output in clinical context.
- **Intended environment:** screening, monitoring and research support. Every
  output is framed as "for clinician review".

## Out of scope / non-diagnostic limitations

- It does **not** diagnose Parkinson's disease, stroke, neuropathy, or any
  condition. It may surface *possible patterns* (e.g. "mild temporal asymmetry")
  for review.
- It does **not** produce a "fall-risk diagnosis". The **Mobility Risk Support
  Score** is a cautious screening aid only.
- It is not a substitute for instrumented gait labs, marker-based motion capture,
  or validated clinical scales.

## Required human oversight

A qualified clinician must review all outputs and combine them with patient
history and physical examination before any clinical decision. The system is
designed to make its uncertainty visible (per-metric confidence, quality scores,
limitations, and an explicit interpretation-limited flag when quality is low).

## Language policy (enforced in code)

- **Allowed:** "AI-assisted gait quantification", "possible mobility pattern
  detected", "requires clinical interpretation", "clinician review recommended",
  "not a standalone diagnosis".
- **Prohibited:** disease names as conclusions, "definitive diagnosis",
  "guaranteed fall risk". The narrative generator (`pipeline/narrative.py`) is
  guard-railed and the LLM seam inherits the same constraints.

## Known failure modes

| Failure mode | Behaviour / mitigation |
| --- | --- |
| **Poor video quality** (dark, blurred, low-res, shaky) | Quality score drops; an "interpretation limited by video quality" flag is raised; metric confidence is reduced. |
| **Multiple people in frame** | Detection guard raises `multiple_people`; analysis stops with guidance to isolate one subject. |
| **No / partial person** | Coverage check raises `no_person` if the subject is not reliably tracked. |
| **Feet not visible** | Event timing degrades; feet-visibility score and limitations flag this. |
| **No spatial calibration** | Walking speed/stride length are approximate or omitted and clearly labelled. |
| **Out-of-plane / oblique camera** | Sagittal metrics (ROM, event timing) lose accuracy; view is estimated and reported. |
| **Few gait cycles** | Variability/asymmetry estimates are limited; flagged in limitations. |
| **Demo / fallback mode** | All output labelled "simulated / fallback — not clinical-grade". |

## Population & device limitations (bias risks)

- **Camera angle / framing:** accuracy assumes a clear, full-body side view.
- **Pediatric & elderly gait** differ from healthy-adult reference ranges; the
  built-in reference values are orientation only and require cohort-specific
  validation.
- **Assistive devices** (canes, walkers, crutches) and **orthoses** alter pose
  and event detection; not validated.
- **Wheelchair users** are **out of scope** (no walking gait to quantify).
- **Clothing/occlusion** (long skirts, baggy trousers, bags) reduce keypoint
  reliability.
- **Dataset bias:** any future trained components must be evaluated across age,
  sex, body habitus, skin tone, footwear and assistive-device subgroups.

## Data protection

- De-identified cases by default (codes/initials, not names).
- Local-only storage in development; no third-party upload without an explicit
  architecture decision and DPA/BAA where applicable.
- Per-video delete endpoint supports data-minimisation requests.
- Role-ready architecture (clinician / admin / patient) for future access control
  and audit logging.

## Regulatory posture

Clinical claims (accuracy, fall-risk, diagnostic support) require the validation
described in [validation_plan.md](validation_plan.md). A production deployment
intended for clinical use would need a QMS (e.g. ISO 13485), risk management
(ISO 14971), clinical evaluation, and EU MDR / FDA pathway assessment. None of
these are claimed here.
