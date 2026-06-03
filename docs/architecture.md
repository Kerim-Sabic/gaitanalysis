# Horalix Gait AI — Architecture

Horalix is built as a **measurement system**, not a chatbot looking at a video.
Every stage is a small, replaceable module behind a typed interface, so heavy AI
models (RTMPose, SAM 2, WHAM, …) can be plugged in without touching the gait
math or the UI.

## System flow

```
Patient walking video
      │
      ▼
┌─────────────────┐
│ VideoProcessor  │  decode, fps/duration/resolution, rotation, normalize frames
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ PoseEstimator   │  COCO-17 keypoints over time   (adapter: MMPose / MediaPipe / Simulated)
│   (adapter)     │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ PersonDetection │  dominant-subject selection, coverage, multi-person guard
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ TemporalSmooth  │  low-confidence rejection → gap interpolation → One Euro filter
└─────────────────┘
      │
      ├──────────────► QualityAssessment  (lighting, blur, resolution, stability, visibility, view)
      ▼
┌─────────────────┐
│ GaitEvents      │  Zeni coordinate-based heel-strike / toe-off detection
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ GaitMetrics     │  cadence, step/stride times, stance/swing, ROM, asymmetry,
│                 │  speed (calibrated/estimated), variability, trunk sway, risk score
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ ClinicalFlags   │  cautious, non-diagnostic pattern flags + confidence
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Narrative /     │  templated clinician + patient summary (LLM seam, guard-railed)
│ ReportGenerator │  → JSON, PDF, skeleton overlay
└─────────────────┘
      │
      ▼
  Clinician review
```

## Module map (`apps/api/app`)

| Module | Responsibility |
| --- | --- |
| `pipeline/video_processor.py` | Decode, validate, normalize frames (OpenCV). Caps frames/long-edge for bounded memory; records `sampled_stride` so timestamps stay correct. |
| `pipeline/pose/` | Model-agnostic pose adapters. `base.py` defines `BasePoseEstimator` + the COCO-17 convention. `factory.select_pose_estimator()` resolves the configured backend, falling back to the **simulated** estimator (demo mode) if no real model is installed. |
| `pipeline/segmentation/` | SAM 2 person-masking adapter (placeholder + `NullSegmenter`). |
| `pipeline/tracking/` | Dominant-subject selection and multi-person guard. |
| `pipeline/smoothing.py` | One Euro filter + short-gap interpolation + low-confidence rejection. |
| `pipeline/quality.py` | Frame- and pose-based quality scoring (0–100) with warnings/recommendations. |
| `pipeline/events.py` | Coordinate-based gait-event detection (Zeni et al. 2008). |
| `pipeline/metrics.py` | All gait metrics, asymmetry, joint curves, Mobility Risk Support Score, calibration. |
| `pipeline/reference.py` | Orientation reference ranges + interpretation banding (not diagnostic thresholds). |
| `pipeline/flags.py` | Cautious clinical flags with supporting metrics + confidence. |
| `pipeline/narrative.py` | Deterministic clinician/patient summaries; **single LLM integration seam** with guardrails. |
| `pipeline/orchestrator.py` | Wires the stages, emits progress, builds the result + pose track. |
| `reporting/` | JSON (Pydantic), PDF (ReportLab), overlay video (OpenCV). |
| `services/analysis_service.py` | Background job runner (ThreadPoolExecutor; queue-shaped for Celery/RQ). |
| `routes/` | FastAPI endpoints for cases, videos, analysis. |
| `storage.py` | SQLite + JSON-file repository (PostgreSQL/S3-ready interface). |

## The keypoint contract

We standardise on **COCO-17**. Every mainstream model can emit it (RTMPose,
ViTPose, OpenPose-mapped, MediaPipe-remapped). Optional COCO-WholeBody foot
points (heel/big-toe) improve event timing; when absent the event detector uses
the ankle as a proxy and records the limitation. A `PoseSequence` is simply an
`(T, 17, 3)` array of `(x, y, score)` plus fps/size/timestamps — the only data
contract the gait math depends on.

## Pose-backend selection (`HORALIX_POSE_BACKEND`)

```
auto      → best installed real model, else Simulated (demo)
mmpose    → MMPose RTMPose/RTMW3D (if installed), else Simulated
mediapipe → MediaPipe BlazePose→COCO-17 (if installed), else Simulated
simulated → always the simulated estimator (demo)
```

`AnalysisMode` (`clinical` vs `demo`) follows from the chosen backend and is
surfaced everywhere (UI badge, PDF, JSON, overlay) so demo output is never
mistaken for clinical-grade output.

## Future model adapters (where to plug them in)

- **MMPose RTMPose / RTMW3D** — fill in `pipeline/pose/mmpose_adapter.py`
  (`_ensure_model` + batched inference). Recommended research-grade 2D/3D path.
- **ViTPose++** — add a sibling adapter implementing `BasePoseEstimator`; highest
  offline 2D accuracy.
- **SAM 2** — implement `segmentation/sam2_adapter.py` for temporally-consistent
  person masks (clutter robustness, clean overlay compositing).
- **WHAM** — add a 3D adapter returning `estimate_3d_pose()` for world-grounded
  3D motion → true foot clearance, 3D joint angles.
- **Depth Anything V2** — optional monocular depth to disambiguate scale.
- **ByteTrack / RTMDet** — promote `tracking/` to operate on raw frames before
  pose for robust multi-person scenes.
- **OpenCap-style multi-camera triangulation** — future capture mode; the
  metrics layer already consumes a generic `PoseSequence`, so 3D triangulated
  keypoints slot in directly.

**Design rule:** the core system must never depend on a single model. All access
is through `BasePoseEstimator` / `BaseSegmenter` adapters.

## Frontend (`apps/web`)

Next.js App Router + TypeScript + Tailwind + Framer Motion + Recharts. The
browser talks to one origin: `/api/*` is rewritten to the FastAPI backend
(`next.config.mjs`). Shared types live in `packages/shared` and are imported by
both the typed API client and the components, keeping the contract in one place.

The results viewer renders the skeleton on a **canvas driven by the pose track**
(codec-independent), overlaying the real `<video>` for clinical uploads and using
a synthesized background for demo runs.

## Data & privacy

Cases are de-identified by default (patient codes/initials). Videos are stored
locally under `data/uploads` and can be deleted via `DELETE /videos/{id}`.
Analysis artefacts (result JSON, pose track) live in `data/processed`. See
[clinical_safety.md](clinical_safety.md).
