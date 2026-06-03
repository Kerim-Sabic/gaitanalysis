# Validation Plan

This plan makes explicit that **clinical claims require validation**. The current
build is a technically-working measurement pipeline; the numbers below are the
acceptance targets a validation program would aim to confirm, not claims about
the present system.

## Stage 1 — Technical validation (open data)
- **Data:** public walking datasets (e.g. treadmill/overground RGB with reference
  events), plus internally recorded clips spanning camera angles, lighting,
  framerates and resolutions.
- **Goal:** verify the pipeline runs robustly, degrades gracefully, and that
  quality/confidence scores track real capture quality.
- **Checks:** event-detection sanity vs. manual frame labelling; failure-mode
  triggers (no person, multiple people, poor quality) fire correctly.

## Stage 2 — Internal repeatability (test–retest)
- Same subject, repeated walks/sessions; quantify within-subject variability.
- **Targets (illustrative):** cadence ICC > 0.9; step-time asymmetry test–retest
  difference within clinically negligible bounds.

## Stage 3 — Agreement with manual physiotherapist annotation
- Physiotherapists annotate heel-strike / toe-off frames and rate reports.
- **Targets:** heel-strike detection F1 ≥ 0.95 within ±2 frames; toe-off ±3
  frames; report usefulness rated acceptable by reviewers.

## Stage 4 — Agreement with clinical scales / instruments
- **Gait speed:** vs. timed/instrumented walkway (target MAE ≤ 0.1 m/s with
  calibration).
- **Cadence:** vs. manual count / footswitches (target MAE ≤ 3 steps/min).
- **Timed Up and Go:** total + phase timings vs. stopwatch / sensor reference.
- **6-minute walk:** distance/speed vs. measured course.
- **Balance/mobility context:** Berg Balance Scale, where available, to
  contextualise the Mobility Risk Support Score (association study, not a claim
  of equivalence).

## Stage 5 — Concurrent validity vs. marker-based motion capture (where feasible)
- Simultaneous Horalix + optical mocap (e.g. Vicon/OptiTrack) or IMU reference.
- **Targets (illustrative):** sagittal knee/hip angle RMSE within published
  markerless tolerances; spatiotemporal parameters within reference CIs.

## Stage 6 — Prospective pilot in physiotherapy / rehab
- Real clinical workflow, intended users, intended environment.
- Outcomes: usability, time-to-report, clinician trust, and impact on decisions
  (qualitative + quantitative), plus safety event monitoring.

## Metrics tracked across stages
- Step / event detection accuracy (precision, recall, F1, timing error)
- Cadence error (MAE, bias)
- Gait-speed error (MAE, Bland–Altman bias & LoA)
- Left–right asymmetry agreement
- Joint-angle error (RMSE per joint)
- Test–retest reliability (ICC, CV)
- Inter-rater agreement (Horalix vs. clinicians; clinician vs. clinician)
- **False-flag rate** (specificity of clinical flags) and missed-pattern rate
- Report usefulness / clinician acceptance

## Subgroup analysis (bias)
All accuracy metrics stratified by age band, sex, body habitus, skin tone,
footwear, camera view and assistive-device use. Performance gaps are documented
and gated before any clinical claim.

## Governance
- Pre-registered analysis plan; frozen pipeline version per study.
- `model_info.pipeline_version` and `pose_model_version` recorded in every result
  for traceability.
- Adverse-pattern review: any case where the tool's flag conflicts with clinical
  judgement is logged and reviewed.
