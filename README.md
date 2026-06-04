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

It is **model-agnostic**: real pose backends are adapters selected through a
transparent quality comparator. Real uploads never silently fall back to
simulated data. The simulated estimator is available only through explicit demo
mode; the gait math still measures that synthetic motion and labels it clearly.

## What's real vs. demo

| Real (computed) | Demo / fallback |
| --- | --- |
| Video decode, quality scoring, smoothing (One Euro filter) | Simulated COCO-17 keypoints from a sagittal walking model when no pose model is installed |
| Gait-event detection (Zeni coordinate method), all metrics, asymmetry, ROM, variability, Mobility Risk Support Score | Demo presets (`normal`, `asymmetric`, `poor_quality`, `tug`) parameterise the simulator; metrics are then genuinely measured from it |
| Confidence/quality-driven flags, JSON + PDF report, overlay rendering | Demo runs render a neutral figure so quality scoring is genuine and a clip is playable |
| Verified MediaPipe Full/Heavy and Ultralytics adapters; transparent real-only auto selection | MMPose/SAM2/Depth/WHAM are reported as blocked until their full runtimes and required assets verify |

Every demo result is labelled `analysis_mode = demo_simulated` in the UI, PDF and JSON.

## Architecture (text diagram)

See **[docs/architecture.md](docs/architecture.md)** for the full module map and
model-adapter plug-in points. Summary:

```
apps/
  api/   FastAPI · OpenCV · NumPy · SciPy · ReportLab · SQLite (PostgreSQL-ready)
  web/   Next.js (App Router) · TypeScript · Tailwind · Framer Motion · Recharts
packages/
  shared/  TypeScript contract mirrored from the Pydantic schemas
models/    local ignored pose/segmentation/tracking/depth weights and configs
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
python scripts/smoke_test.py            # runs all four demo presets
python apps/api/scripts/integration_test.py  # end-to-end against a running server
```

### Real AI Vision Setup

The default real backend is **MediaPipe Tasks PoseLandmarker** (`mediapipe_tasks`),
which loads a local `.task` model and provides heel/foot_index landmarks. A real
fallback **`ultralytics_pose`** (YOLOv8-Pose, COCO-17, no feet) is also supported.

**Windows (PowerShell):**

```powershell
cd apps/api
py -3.11 -m venv .venv-real
.venv-real\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-real.txt

python ../../scripts/model_inventory.py            # weights/runtimes/backends
python ../../scripts/verify_models.py              # init + real inference
python ../../scripts/model_healthcheck.py          # full real-analysis chain
python ../../scripts/test_pose_on_sample_video.py  # needs data/sample_videos/walk_test.mp4
```

Run the backend (default backend is `auto_best`, which compares real backends only):

```powershell
$env:HORALIX_POSE_BACKEND="auto_best"   # or mediapipe_tasks_full / mediapipe_tasks_heavy / ultralytics_pose / demo
uvicorn app.main:app --port 8000
```

The MediaPipe `.task` model is resolved from `HORALIX_MEDIAPIPE_MODEL_PATH`, then
`models/pose/mediapipe/pose_landmarker_full.task`, then
`apps/api/models/mediapipe/pose_landmarker_full.task`.

**If a package mirror serves a hollow MediaPipe stub** (imports but lacks the
inference runtime), reinstall from official PyPI, or use Docker:

```powershell
python -m pip uninstall -y mediapipe
python -m pip install --index-url https://pypi.org/simple mediapipe
# or, fully isolated:
docker compose --profile real up --build api-real
```

**Real vs Demo (hard separation).** Uploaded videos run **real** inference
(`analysis_mode = real_mediapipe_tasks` or `real_ultralytics_pose`,
`simulated_data_used = false`). If the configured real backend is unavailable,
real analysis **fails clearly** with *"Real pose model is unavailable. Run model
setup or switch to Demo Mode."* — it never silently falls back. Demo Mode
(`analysis_mode = demo_simulated`) uses simulated keypoints, is clearly labelled
"not real patient analysis", and is never auto-selected for uploads.

**FULL REAL VERIFIED requires a real walking video** at
`data/sample_videos/walk_test.mp4` (see that folder's README). Without it, the
scripts report **MODEL EXECUTION VERIFIED ONLY** (model loads + runs inference,
but landmarks need a real human).

**Verify it's really running:** `GET /models/status` and `GET /models/verify`
report whether a real model imported, initialized and produced landmarks. The
results page **Model transparency** panel and PDF/JSON show the same provenance
(`model_loaded`, `model_verified`, `simulated_data_used`, device, frame counts).

**Reading keypoint colors (Keypoint Analysis tab).** Colours describe *tracking
reliability*, not disease: **green** ≥ 0.80 reliable · **yellow** 0.60–0.79
moderate · **orange** 0.40–0.59 low/occluded · **red** < 0.40 unreliable/missing
· **dashed ring** = interpolated estimate. A separate "Movement flags" mode shows
whether a *metric* derived from a joint needs review — a joint can be tracked
well while its movement metric is flagged.

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
| **MediaPipe Full/Heavy** (real 2D + feet) | `pipeline/pose/mediapipe_adapter.py` | `pip install mediapipe`, set `HORALIX_POSE_BACKEND=mediapipe_tasks_full` or `mediapipe_tasks_heavy`. |
| **Ultralytics Pose** (real COCO-17 fallback) | `pipeline/pose/ultralytics_adapter.py` | `pip install -r requirements-real.txt`; foot metrics are explicitly reduced-confidence. |
| **MMPose RTMW/RTMW3D** (research-grade) | `pipeline/pose/mmpose_adapter.py` | Requires matching config + checkpoint. Use the MMPose Docker profile when local OpenMMLab is incompatible. |
| **SAM 2** (person masking) | `pipeline/segmentation/sam2_adapter.py` | Checkpoint presence alone is not treated as working; video-mask propagation remains blocked until verified. |
| **WHAM** (monocular 3D) | add a `BasePoseEstimator` returning `estimate_3d_pose()` | enables true foot clearance & 3D angles. |
| **LLM reporting** | `pipeline/narrative.py` (`generate_with_llm`) | receives structured metrics only; guardrails enforced (no invented values, no diagnosis). |

Config via env (prefix `HORALIX_`): `HORALIX_POSE_BACKEND`, `HORALIX_ALLOW_DEMO_MODE`,
`HORALIX_DATABASE_URL`, … (see `apps/api/app/config.py`).

## Advanced Vision Models

Supported pose backend values are `auto_best`, `mediapipe_tasks_full`,
`mediapipe_tasks_heavy`, `mmpose_rtmw`, `mmpose_rtmw3d`, `ultralytics_pose`,
and explicit `demo`. `auto_best` runs available real backends, scores measured
pose coverage/confidence/foot quality/jitter/events, and never selects demo.

```powershell
apps/api/.venv/Scripts/python.exe scripts/select_best_gait_sample.py
apps/api/.venv/Scripts/python.exe scripts/model_inventory.py
apps/api/.venv/Scripts/python.exe scripts/verify_all_vision_models.py
apps/api/.venv/Scripts/python.exe scripts/verify_ultralytics.py
apps/api/.venv/Scripts/python.exe scripts/verify_mmpose.py
apps/api/.venv/Scripts/python.exe scripts/verify_sam2.py
apps/api/.venv/Scripts/python.exe scripts/verify_depth_anything.py
```

```bash
docker compose --profile real up --build api-real
docker compose --profile mmpose up --build api-mmpose
docker compose --profile vision up --build api-vision
```

MMPose requires the checkpoint's matching config at
`models/pose/rtmw/configs/rtmw-x_384x288.py`. SAM2 and Depth Anything remain
optional until actual inference output is verified. WHAM remains
`blocked_missing_smpl_assets` unless legally obtained SMPL model files exist.

`FULL MULTI-MODEL VERIFIED` requires best-sample selection, working MediaPipe
Full and Heavy, at least one advanced real backend, a passing real HTTP upload
with `simulated_data_used=false`, JSON/PDF/UI provenance, and explicit demo mode.

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
