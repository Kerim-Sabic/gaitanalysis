<div align="center">

# Horalix Gait AI

**Markerless AI gait analysis from ordinary walking video.**

AI-assisted gait quantification → skeleton overlays, gait metrics, left–right
asymmetry, confidence scoring, cautious clinical flags, and a clinician-ready
report. _For clinician review — not a standalone diagnosis._

</div>

---

## What this is

Horalix turns a single smartphone walking clip into structured, objective gait
metrics. It is built as a **measurement system**, with a modular pipeline:

```
video → quality check → person tracking → pose estimation → temporal smoothing →
gait-event detection → metrics → confidence scoring → clinical flags → report
```

It is **model-agnostic**: pose backends (MMPose/RTMPose, MediaPipe, ViTPose,
WHAM, SAM 2 …) are adapters. When no heavy model is installed it falls back to a
**simulated** estimator and clearly labels the output as demo / not clinical-grade
— the gait math is still real and *measures* the (synthetic) motion; nothing is
hard-coded.

## What's real vs. demo

| Real (computed) | Demo / fallback |
| --- | --- |
| Video decode, quality scoring, smoothing (One Euro filter) | Simulated COCO-17 keypoints from a sagittal walking model when no pose model is installed |
| Gait-event detection (Zeni coordinate method), all metrics, asymmetry, ROM, variability, Mobility Risk Support Score | Demo presets (`normal`, `asymmetric`, `poor_quality`, `tug`) parameterise the simulator; metrics are then genuinely measured from it |
| Confidence/quality-driven flags, JSON + PDF report, overlay rendering | Demo runs render a neutral figure so quality scoring is genuine and a clip is playable |
| Adapters for MediaPipe (real, optional) | MMPose / SAM 2 / WHAM adapters are integration-ready placeholders |

Every demo result is labelled `analysis_mode = demo` in the UI, PDF and JSON.

## Architecture (text diagram)

See **[docs/architecture.md](docs/architecture.md)** for the full module map and
model-adapter plug-in points. Summary:

```
apps/
  api/   FastAPI · OpenCV · NumPy · SciPy · ReportLab · SQLite (PostgreSQL-ready)
  web/   Next.js (App Router) · TypeScript · Tailwind · Framer Motion · Recharts
packages/
  shared/  TypeScript contract mirrored from the Pydantic schemas
models/    placeholders for pose/segmentation/tracking/gait weights
data/      uploads / processed / reports (git-ignored)
docs/      architecture · clinical_safety · validation_plan · api
```

## Quick start

### Prerequisites
Python 3.10+ and Node 18+.

### 1) Backend (FastAPI)

```bash
cd apps/api
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs at <http://localhost:8000/docs>. Health at `/health`.

Smoke-test the pipeline without the server:

```bash
python scripts/smoke_test.py        # runs all four demo presets
python scripts/integration_test.py  # end-to-end against a running server
```

### 2) Frontend (Next.js)

```bash
cd apps/web
cp .env.local.example .env.local     # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open <http://localhost:3000>. Click **“See it work — instant demo”** to run the
full pipeline immediately (no upload needed).

### Or with Docker

```bash
docker compose up --build
# web → http://localhost:3000   api → http://localhost:8000
```

## Using the app

1. **New analysis** → create a de-identified case (code/initials).
2. Pick a **test type** (Standard walk, Timed Up and Go, 6-minute walk,
   Sit-to-stand, Post-op mobility, Neuro gait screen).
3. **Upload** a walking video (full body, side view, steady camera).
4. Review the **quality check** (lighting, sharpness, resolution, stability,
   framerate, duration). Fix issues if flagged.
5. **Run analysis** → watch the staged progress → land on the **results**:
   skeleton overlay with scrub + toggles, metric cards, joint-angle curves,
   left–right asymmetry, Mobility Risk Support Score, clinical flags, model
   transparency, and limitations.
6. Open the **report** and export **PDF** / **JSON**.

## Plugging in real models

| Model | File | Steps |
| --- | --- | --- |
| **MediaPipe** (real 2D, easiest) | `pipeline/pose/mediapipe_adapter.py` | `pip install mediapipe`, set `HORALIX_POSE_BACKEND=auto` or `mediapipe`. |
| **MMPose RTMPose/RTMW3D** (research-grade 2D/3D) | `pipeline/pose/mmpose_adapter.py` | `mim install mmengine mmcv mmpose`, fill the inference TODO, set `HORALIX_POSE_BACKEND=mmpose`. |
| **SAM 2** (person masking) | `pipeline/segmentation/sam2_adapter.py` | install `sam2` + checkpoint, implement `segment_person`. |
| **WHAM** (monocular 3D) | add a `BasePoseEstimator` returning `estimate_3d_pose()` | enables true foot clearance & 3D angles. |
| **LLM reporting** | `pipeline/narrative.py` (`generate_with_llm`) | receives structured metrics only; guardrails enforced (no invented values, no diagnosis). |

Config via env (prefix `HORALIX_`): `HORALIX_POSE_BACKEND`, `HORALIX_ALLOW_DEMO_MODE`,
`HORALIX_DATABASE_URL`, … (see `apps/api/app/config.py`).

## Limitations & validation

This is an investor/clinical-pilot-grade demo of a real architecture. Clinical
claims require the program in **[docs/validation_plan.md](docs/validation_plan.md)**.
Read **[docs/clinical_safety.md](docs/clinical_safety.md)** for intended use,
non-diagnostic limitations and known failure modes. Single-camera 2D analysis
limits depth and out-of-plane accuracy; speed/stride length need calibration;
wheelchair users and assistive devices are out of scope / unvalidated.

> This analysis is intended to support clinical review and should not be used as
> a standalone diagnostic decision.

## Roadmap

Multi-camera capture · OpenCap-style triangulation · calibrated walking-distance
setup · smartphone capture app · physiotherapist annotation tool · rehabilitation
progress tracking & visit comparison · EMR/PACS integration · clinician review
workflow & audit logging · regulatory QMS documentation · EU MDR readiness.

## License

Prototype for demonstration and research. Not a medical device. No clinical use
without validation and appropriate regulatory clearance.
