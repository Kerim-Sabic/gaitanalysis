# Next Implementation Context: Horalix Gait AI

Use this as source-of-truth context for the next coding agent. Do not rely on README claims without rechecking code.

## Current Verified State

Repository: `c:\Users\kerim\gaitanalysis`  
Branch: `feature/real-model-loading-keypoint-analysis`  
Audit date: 2026-06-03  

Current verdict: **demo pipeline works; real uploaded-video inference is blocked**.

No app source changes or commits were made during the audit. Two audit files were created:

- `CODEX_AUDIT_HORALIX_GAIT_AI.md`
- `NEXT_IMPLEMENTATION_CONTEXT.md`

## What Works

- FastAPI app and route structure exist.
- Next.js frontend builds with `npm run build`.
- Demo analysis works end-to-end through backend HTTP integration.
- Demo pipeline produces pose track, keypoint stats, metrics, model-status, JSON, and PDF.
- `/analysis/start` does not silently fallback to demo; it returns 422 `model_unavailable` when real backend is unavailable.
- Keypoint Analysis UI is real, not just a mock:
  - canvas skeleton overlay
  - keypoint confidence colors
  - movement flag colors
  - both/hide color modes
  - clickable keypoints
  - details panel
  - confidence chart
  - low-confidence keypoint list
  - left/right leg tracking quality
  - gait-event markers
- PDF and JSON exports work for demo.
- Model transparency exists in stored result, report, and UI.

## What Does Not Work

Critical blocker:

- Current MediaPipe adapter uses `mediapipe.solutions.pose`.
- Installed `mediapipe==0.10.35` in `apps/api/.venv` has `mediapipe.tasks` but no `mediapipe.solutions`.
- `scripts/verify_models.py` fails with `ModuleNotFoundError: No module named 'mediapipe.solutions'`.
- `scripts/model_healthcheck.py` fails at `backend_resolved`.
- `/models/status` reports real analysis unavailable.
- Real uploaded-video analysis cannot complete.

Important gaps:

- The local `.task` files are present but not used by the app.
- `mediapipe.tasks.python.vision.PoseLandmarker` imports successfully.
- A manual probe initialized `models/pose/mediapipe/pose_landmarker_full.task` and ran inference on a synthetic frame, but no landmarks were detected because it was synthetic.
- No real sample walking video exists at `data/sample_videos/walk_test.mp4`.
- MMPose, SAM2, Depth Anything, WHAM, SMPL, detector runtimes are missing.
- MMPose/SAM2 adapters are placeholders/partial.
- No Depth or WHAM adapters exist.
- `reporting/overlay.py` has a demo-label bug: it checks `analysis_mode.value == "demo"` but canonical value is `demo_simulated`.
- `model_loader.verify()` can pass if inference runs even when no landmarks are detected. This must be tightened.
- `model_loader.healthcheck()` should also require valid landmarks.
- `model_loader.status().real_analysis_available` can be inconsistent with the configured backend if one real backend is available but the requested backend is not.
- Docs still mention old fallback and `clinical`/`demo` terminology.

## Local Model Inventory

About 21.44 GB of model files exist under `models/`.

Present:

- MediaPipe:
  - `models/pose/mediapipe/pose_landmarker_lite.task`
  - `models/pose/mediapipe/pose_landmarker_full.task`
  - `models/pose/mediapipe/pose_landmarker_heavy.task`
- SAM2.1 and SAM2 original:
  - all tiny/small/base_plus/large `.pt` files under `models/segmentation`
- MMPose-ish:
  - RTMPose checkpoints under `models/pose/rtmpose`
  - RTMW checkpoints under `models/pose/rtmw`
  - RTMW3D checkpoints under `models/pose/rtmw3d`
  - matching MMPose config files are missing
- Person detectors/tracking:
  - RTMDet nano/m person detector checkpoints under `models/tracking`
  - ByteTrack checkpoint under `models/tracking`
  - YOLOv8x under WHAM checkpoint folder
- Depth Anything V2:
  - Small/Base/Large checkpoints under `models/depth`
- WHAM:
  - WHAM checkpoint files, HMR2A, DPVO, ViTPose-H, YOLOv8x
  - SMPL assets incomplete; no full SMPL neutral/male/female model files found
- ViTPose extra checkpoints exist but are not integrated.

Missing runtime deps:

- `torch`
- `mmpose`
- `mmcv`
- `mmengine`
- `sam2`
- `transformers`
- `depth_anything_v2`
- `wham`
- `smplx`
- `ultralytics`

## Files To Focus On

Backend:

- `apps/api/app/pipeline/pose/mediapipe_adapter.py`
- `apps/api/app/models/model_loader.py`
- `apps/api/app/models/model_registry.py`
- `apps/api/app/pipeline/orchestrator.py`
- `apps/api/app/pipeline/pose/base.py`
- `scripts/verify_models.py`
- `scripts/model_healthcheck.py`
- `scripts/test_pose_on_sample_video.py`
- `apps/api/app/routes/analysis.py`
- `apps/api/app/reporting/overlay.py`

Frontend likely does not need major changes for the MVP real-model fix:

- `apps/web/components/analysis/results-view.tsx`
- `apps/web/components/analysis/keypoint-analysis.tsx`
- `apps/web/components/analysis/transparency.tsx`
- `apps/web/components/viewer/skeleton-canvas.tsx`

## Required MVP Implementation

Implement only the missing MediaPipe Tasks real pose backend. Do not rewrite the app.

1. Add/update MediaPipe adapter to use:
   - `mediapipe.tasks.python.BaseOptions`
   - `mediapipe.tasks.python.vision.PoseLandmarker`
   - `PoseLandmarkerOptions`
   - `RunningMode.VIDEO` or frame-compatible mode
   - local `.task` file path, defaulting to `models/pose/mediapipe/pose_landmarker_full.task`
2. Keep output contract:
   - `PoseSequence`
   - COCO-17 core keypoints
   - extended `left_heel`, `right_heel`, `left_foot_index`, `right_foot_index`
   - timestamps/fps/width/height
3. Preserve hard real/demo separation:
   - real path never returns simulated keypoints
   - demo remains explicit
   - failed model path returns clear errors
4. Tighten verification:
   - `verify_models.py` must fail unless inference runs and real landmarks are detected on a real sample video when available
   - synthetic-only inference should be reported as "execution only", not full verification
   - `model_loader.verify()` should not mark `passed` true if no landmarks are detected unless the script clearly labels it as execution-only
   - `model_healthcheck()` should require nonzero valid pose frames
5. Fix known small correctness issues:
   - server overlay demo warning should check `result.simulated_data_used` or `AnalysisMode.demo_simulated`
   - model status should distinguish "configured backend available" from "some real backend available"
6. Add focused tests or scripts:
   - unit/import test for MediaPipe Tasks adapter
   - verify script for local `.task` model
   - one real sample video test if `data/sample_videos/walk_test.mp4` exists
   - demo smoke must still pass
   - frontend build must still pass

## Do Not Implement Yet

Do not add these until MediaPipe Tasks MVP is working:

- SAM2 segmentation integration
- MMPose/OpenMMLab integration
- Depth Anything integration
- WHAM/SMPL integration
- major frontend redesign
- new clinical features
- new diagnosis/risk claims

## Acceptance Commands

Use the repo venv:

```powershell
apps/api/.venv/Scripts/python.exe scripts/verify_models.py
apps/api/.venv/Scripts/python.exe scripts/model_healthcheck.py
apps/api/.venv/Scripts/python.exe apps/api/scripts/smoke_test.py
npm run build
```

Run `npm run build` from `apps/web`.

For HTTP integration, start a temporary API server and run:

```powershell
apps/api/.venv/Scripts/python.exe apps/api/scripts/integration_test.py http://127.0.0.1:8010
```

If a real walking sample exists:

```powershell
apps/api/.venv/Scripts/python.exe scripts/test_pose_on_sample_video.py
```

## PASTE THIS INTO CLAUDE/CODEX NEXT

You are inside the Horalix Gait AI repository. Use `CODEX_AUDIT_HORALIX_GAIT_AI.md` and `NEXT_IMPLEMENTATION_CONTEXT.md` as source of truth.

Task: implement only the missing MVP real pose path. Do not rewrite the app, do not add SAM2/MMPose/Depth/WHAM features, do not change clinical claims, and do not make broad frontend redesigns.

The current blocker is that `apps/api/app/pipeline/pose/mediapipe_adapter.py` uses `mediapipe.solutions.pose`, but the installed `mediapipe==0.10.35` exposes `mediapipe.tasks` and the local `.task` weights are present. Implement a MediaPipe Tasks PoseLandmarker backend that loads `models/pose/mediapipe/pose_landmarker_full.task` by default, maps Tasks landmarks to the existing `PoseSequence` contract (COCO-17 plus heel/foot_index extras), and preserves hard real/demo separation.

Also tighten model verification so "passed" requires meaningful landmarks, fix the server overlay demo warning check, and make model status distinguish configured-backend availability from any-backend availability. Keep changes small and focused. After implementation, run backend verify, model healthcheck, demo smoke, HTTP integration if possible, and frontend build. Report exactly what passed and what could not be verified.
