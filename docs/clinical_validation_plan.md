# Clinical Validation Plan

> **This version is technically verified for demo use and clinical-review
> support, not clinically validated for diagnosis.** Horalix Gait AI provides
> AI-assisted gait quantification for clinician review. It is not a medical
> device and makes no diagnostic, fall-prediction, or regulatory claims.

## What is technically verified (now)
- Real pose inference runs on uploaded video (MediaPipe Tasks Full/Heavy) and on
  live single frames; Ultralytics YOLO-Pose works as a COCO-17 fallback.
- Real vs demo separation is enforced (`simulated_data_used=false` in real mode;
  no silent fallback).
- Spatiotemporal/kinematic metrics are computed from real keypoints with
  per-metric confidence, source keypoints, and limitations.
- Technical **repeatability** is checked (`benchmark_gait_reliability.py`):
  stable backend selection, valid-frame %, confidence, cadence, step count.
- Provenance (selected backend, scores, model files, timings) is shown in UI,
  JSON and PDF.

## What is NOT validated (explicitly)
- No agreement study against marker-based motion capture (Vicon/OptiTrack).
- No agreement against clinician/physiotherapist gait annotations.
- No condition-specific (Parkinsonian, post-stroke, neuropathic, orthopedic)
  performance characterisation.
- No calibrated spatial accuracy (single-camera 2D; monocular depth is relative).
- No test–retest / inter-device / camera-placement reliability study.

## Required future validation
1. **Concurrent validity** vs marker-based mocap on a shared cohort (joint
   angles RMSE; spatiotemporal MAE/Bland–Altman).
2. **Criterion validity** vs instrumented walkway (GAITRite) for cadence, step
   length, gait speed.
3. **Inter-rater agreement** vs ≥2 clinicians on event timing and asymmetry.
4. **Test–retest reliability** (ICC) across sessions and devices.
5. **Camera-placement sensitivity** (angle, distance, height, fps, resolution).
6. **Subgroup testing** across age, sex, body habitus, skin tone, footwear,
   assistive devices.
7. **Pathology-specific** validation with labelled clinical datasets before any
   pattern-flag is presented as clinically meaningful.
8. **Prospective usability** study with target clinicians.

## Regulatory pathway note
Any diagnostic or screening claim would require a defined intended use, a quality
system (e.g. ISO 13485), risk management (ISO 14971), clinical evaluation, and the
applicable regulatory route (FDA / EU MDR). None are claimed or in progress here.

## Intended-use wording (current)
"AI-assisted gait quantification from video to support clinician review. Outputs
are objective movement measurements with explicit confidence and limitations, and
must not be used as a standalone diagnostic decision."
