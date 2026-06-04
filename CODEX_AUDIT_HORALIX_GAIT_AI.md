# Horalix Gait AI Technical Audit

Audit date: 2026-06-03  
Branch inspected: `feature/real-model-loading-keypoint-analysis`  
Latest local commit: `7c286f2 feat: add real pose model loading and keypoint analysis`  
Git status before report files: model-weight directories are untracked; no app source changes were made.

## Overall Verdict

Current classification: **demo pipeline working, real uploaded-video pipeline blocked**.

The backend has a real-analysis architecture and explicit real/demo separation, but the current real MediaPipe adapter is written for `mediapipe.solutions.pose`. The installed `mediapipe==0.10.35` package in `apps/api/.venv` exposes `mediapipe.tasks` only, not `mediapipe.solutions`, so the configured real backend does not initialize.

Important evidence:

- `python scripts/verify_models.py`: **FAILED**, `ModuleNotFoundError: No module named 'mediapipe.solutions'`.
- `python scripts/model_healthcheck.py`: **FAILED**, `backend_resolved` failed.
- HTTP integration: `/models/status` returned `real_analysis_available: False`, `/models/verify` returned `passed: False`.
- HTTP integration: demo analysis completed with `analysis_mode: demo_simulated`, `simulated_data_used: True`, 15 metrics, 17 keypoint stats, valid PDF.
- HTTP integration: real analysis start returned 422 with `code: model_unavailable`; there was no silent fallback to demo.
- Separate local probe: `mediapipe.tasks.python.vision.PoseLandmarker` imports and initializes with `models/pose/mediapipe/pose_landmarker_full.task`, and inference runs on a synthetic frame, but the current app does not use this API.

## Command Results

| Check | Command/result | Classification |
| --- | --- | --- |
| Python | `Python 3.12.10` globally and in `apps/api/.venv` | VERIFIED WORKING |
| Backend packages | FastAPI/OpenCV/ReportLab installed; `mediapipe 0.10.35` installed | PARTIALLY IMPLEMENTED |
| Missing ML deps | `torch`, `mmpose`, `mmcv`, `mmengine`, `sam2`, `transformers`, `depth_anything_v2`, `wham`, `smplx`, `ultralytics` missing | MISSING |
| CUDA | Torch missing, CUDA could not be checked through torch | MISSING |
| Model files | 94 files, about 21.44 GB under `models/` | VERIFIED PRESENT |
| Model setup | `scripts/download_models.py` ran; MediaPipe functional check failed on `mediapipe.solutions` | BROKEN for current adapter |
| Model verify | `scripts/verify_models.py` failed | BROKEN |
| Model healthcheck | `scripts/model_healthcheck.py` failed | BROKEN |
| Backend demo smoke | `apps/api/scripts/smoke_test.py` passed all four demo presets | VERIFIED WORKING |
| HTTP integration | Temporary API on port 8010 passed demo, keypoints, model-status, PDF, real-start 422 | VERIFIED WORKING for demo/control-plane |
| FastAPI routes | Route enumeration shows all requested route families | VERIFIED PRESENT |
| Frontend build | `npm run build` passed | VERIFIED WORKING |
| Sample real video | `data/sample_videos/walk_test.mp4` not present | MISSING |
| `test_pose_on_sample_video.py` | Inspected but not run; no real sample exists and the script writes JSON/PNG/report artifacts | NOT RUN, EXPLAINED |

OpenCV emitted H.264/OpenH264 warnings during demo smoke video generation but the smoke test completed successfully, likely using fallback codec behavior.

## Backend Architecture

Status: **PARTIALLY IMPLEMENTED**

Main backend stack:

- FastAPI app: `apps/api/app/main.py`
- Routes: `routes/cases.py`, `routes/videos.py`, `routes/analysis.py`, `routes/models.py`
- Background analysis service: `services/analysis_service.py`
- Storage: SQLite plus JSON artifacts in `data/processed` via `storage.py`
- Pipeline orchestrator: `pipeline/orchestrator.py`
- Pose adapters: `pipeline/pose/mediapipe_adapter.py`, `mmpose_adapter.py`, `simulated.py`
- Metrics/events/quality: `pipeline/events.py`, `metrics.py`, `quality.py`, `keypoint_quality.py`, `smoothing.py`
- Reporting: `reporting/pdf_report.py`, `reporting/overlay.py`

The backend pipeline is modular and typed. Demo analysis executes through the same downstream smoothing, events, metrics, confidence, flags, narrative, and reporting path as real analysis, but with simulated input keypoints.

Major backend issue: the only intended MVP real adapter cannot run in this environment because it uses the old MediaPipe Solutions API, while the installed package exposes the Tasks API.

## Frontend Architecture

Status: **VERIFIED WORKING for build and demo UI**

Main frontend stack:

- Next.js App Router: `apps/web/app`
- Typed API client: `apps/web/lib/api.ts`
- Shared API types and keypoint helpers: `packages/shared/src`
- Results UI: `components/analysis/results-view.tsx`
- Keypoint UI: `components/analysis/keypoint-analysis.tsx`
- Canvas overlay: `components/viewer/skeleton-canvas.tsx`
- Model transparency: `components/analysis/transparency.tsx`

`npm run build` succeeded. The frontend has real components for upload, quality review, analysis polling, results, keypoint analysis, PDF/JSON links, model transparency, and demo warnings. It is not just static mock UI.

## API Routes

Status: **VERIFIED PRESENT**

Route enumeration:

- `POST /cases`
- `GET /cases`
- `GET /cases/{case_id}`
- `PATCH /cases/{case_id}/review`
- `POST /videos/upload`
- `GET /videos/{video_id}`
- `GET /videos/{video_id}/quality`
- `GET /videos/{video_id}/raw`
- `DELETE /videos/{video_id}`
- `POST /analysis/start`
- `POST /analysis/demo`
- `GET /analysis/{analysis_id}/status`
- `GET /analysis/{analysis_id}/result`
- `GET /analysis/{analysis_id}/pose`
- `GET /analysis/{analysis_id}/keypoints`
- `GET /analysis/{analysis_id}/model-status`
- `GET /analysis/{analysis_id}/report.json`
- `GET /analysis/{analysis_id}/report.pdf`
- `GET /analysis/{analysis_id}/overlay-video`
- `GET /models/status`
- `GET /models/verify`
- `GET /models/healthcheck`
- `GET /`
- `GET /health`

Endpoint quality:

- `/models/status`: route works, but `real_analysis_available` is computed as any available real backend, not necessarily the configured backend. This can become wrong if, for example, `HORALIX_POSE_BACKEND=mmpose_future` is unavailable while MediaPipe is available.
- `/models/verify`: route exists, but the pass criterion in `model_loader.py` is too weak. It sets `passed = initialized and inference_ran`; it does not require landmarks to be detected.
- `/models/healthcheck`: route exists, but it can accept zero-landmark synthetic output if the metrics pipeline accepts it.
- `/analysis/{id}/keypoints`: verified in HTTP integration for demo; returned 17 stats and 210 frames.
- `/analysis/{id}/model-status`: verified in HTTP integration for demo; returned stored model provenance.

## Real vs Demo Separation

Verdict: **PARTIALLY IMPLEMENTED, mostly honest**

Current behavior:

- Demo mode is explicit through `POST /analysis/demo` or `demo_preset`.
- Demo result uses `analysis_mode = demo_simulated`.
- Demo result uses `simulated_data_used = true`.
- Uploaded-video real analysis does not silently fall back to demo.
- If no real backend is available, `POST /analysis/start` returns HTTP 422 `model_unavailable`.

Verified via HTTP integration:

- Demo completed: `analysis_mode: demo_simulated`, `simulated_data_used: True`, `pose_backend: demo`.
- Real start on the demo video returned 422 `model_unavailable`.

Problems:

- `docs/architecture.md` and parts of `README.md` still describe older fallback behavior and older names like `clinical`/`demo`; this is stale relative to current code.
- `pipeline/pose/factory.py` still exports an old fallback selector that can return simulated estimators for real backend requests. Current orchestrator does not use it, but it is stale and risky.
- `reporting/overlay.py` checks `result.analysis_mode.value == "demo"`, but canonical demo value is `demo_simulated`. Demo warning text will not be drawn on downloaded server-side overlay videos.
- The UI component `DemoBadge` says "simulated / fallback analysis"; current real analysis does not fallback, so wording should be tightened later.

Answer to required question: **Real uploaded video currently uses real model inference: NO.**

Reason: MediaPipe current adapter fails import/availability checks, model verify fails, model healthcheck fails, `/models/status` says real analysis unavailable, and `/analysis/start` fails fast with 422.

## Video Upload and Analysis Flow

Text flow diagram:

`apps/web/app/analyze/page.tsx`
-> `POST /cases`
-> `POST /videos/upload`
-> save file under `data/uploads`
-> OpenCV probe in `VideoProcessor.probe`
-> `GET /videos/{id}/quality`
-> `POST /analysis/start`
-> model availability gate
-> background `AnalysisService`
-> `GaitPipeline.run`
-> decode frames
-> select pose estimator
-> pose inference or simulated pose
-> person detection guard
-> smoothing/interpolation
-> quality with pose visibility
-> keypoint stats
-> gait events
-> gait metrics
-> confidence refinement
-> flags/narrative/model info
-> save JSON result and pose track
-> frontend polls `/analysis/{id}/status`
-> renders `/result` and `/pose`
-> exports `/report.json`, `/report.pdf`, `/overlay-video`

Step status:

| Step | File/function | Status | Evidence / issue |
| --- | --- | --- | --- |
| Frontend upload | `apps/web/app/analyze/page.tsx` | VERIFIED WORKING by build | Creates case, uploads FormData, checks quality, starts analysis |
| Backend upload | `routes/videos.py::upload_video` | VERIFIED PRESENT | Validates case, suffix, 400 MB cap, writes `data/uploads`, probes video |
| Saved video path | `settings.uploads_dir` | VERIFIED PRESENT | Stored in `VideoMetadata.stored_path` |
| Frame extraction | `pipeline/video_processor.py` | VERIFIED PRESENT | Used by quality and pipeline |
| Quality assessment | `pipeline/quality.py` | VERIFIED WORKING for demo/smoke | Pre-analysis lacks pose visibility until analysis |
| Pose backend selection | `model_loader.get_real_estimator` | BROKEN in current env | MediaPipe Solutions unavailable |
| Pose inference | `mediapipe_adapter.py` | BROKEN current app | Adapter uses `mediapipe.solutions`; Tasks API exists but unused |
| PoseSequence creation | `pose/base.py` and adapters | VERIFIED for demo; not verified real app | Demo produces track; current real cannot reach this |
| Smoothing | `pipeline/smoothing.py` | VERIFIED WORKING for demo | Smoke succeeded |
| Gait events | `pipeline/events.py` | PARTIALLY IMPLEMENTED | Uses ankle proxy only, not heel/toe extras |
| Metrics | `pipeline/metrics.py` | VERIFIED WORKING for demo | 15 metrics in HTTP integration |
| Flags | `pipeline/flags.py` | VERIFIED WORKING for demo | Smoke produced expected flags |
| Overlay generation | `reporting/overlay.py` | PARTIAL | Code exists; demo label check broken; not HTTP-tested in audit |
| Result storage | `storage.py` | VERIFIED WORKING | Demo integration loaded result/pose |
| Frontend results | `results-view.tsx` | VERIFIED WORKING by build | Requires backend data to render |
| PDF export | `pdf_report.py` | VERIFIED WORKING for demo | HTTP integration returned valid PDF bytes |
| JSON export | `routes/analysis.py::report_json` | VERIFIED WORKING for demo | Returns Pydantic result |

## Model Inventory

Overall local model storage: **94 files, about 21.44 GB** under `models/`.

| Family | Installed/present | Paths and sizes | Dependency status | Adapter status | App inference verified | Result format | Pipeline integration | Limitations | Exact next step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MediaPipe Pose Landmarker Lite/Full/Heavy | YES | `models/pose/mediapipe/pose_landmarker_lite.task` 5.51 MB; `pose_landmarker_full.task` 8.96 MB; `pose_landmarker_heavy.task` 29.24 MB | `mediapipe 0.10.35` installed; `mediapipe.tasks` works; `mediapipe.solutions` missing | BROKEN for current app; adapter uses Solutions API and ignores `.task` files | Current app: NO. Separate Tasks probe initialized full task and ran inference; no synthetic landmarks | Would produce 33 landmarks from Tasks API, needs mapping to COCO-17 + feet | NO current integration | No real sample video; must implement Tasks API adapter | Implement MediaPipe Tasks PoseLandmarker adapter using local `.task`, map landmarks to `PoseSequence`, update verify/healthcheck |
| SAM 2.1 | YES | `models/segmentation/sam2.1_hiera_tiny.pt` 148.78 MB; small 175.87 MB; base_plus 308.62 MB; large 856.48 MB | `sam2` and `torch` missing | PLACEHOLDER ONLY in `sam2_adapter.py`; `segment_person` raises `NotImplementedError` | NO | None | NO | Optional for masking, not required for MVP gait metrics | Install SAM2 deps later and implement person mask adapter after MVP pose works |
| SAM 2 original | YES | `sam2_hiera_tiny.pt` 148.68 MB; small 175.77 MB; base_plus 308.51 MB; large 856.35 MB | `sam2` and `torch` missing | PLACEHOLDER ONLY | NO | None | NO | Redundant until adapter exists | Defer; prefer SAM2.1 Tiny first if needed |
| MMPose RTMW / RTMW3D / RTMPose | YES weights | RTMW-X 384x288 352.59 MB; RTMW3D-X 353.13 MB; RTMPose X 188.95 MB; multiple smaller RTMPose/RTMW files | `torch`, `mmpose`, `mmcv`, `mmengine` missing | PARTIAL/PLACEHOLDER; `mmpose_adapter.py` imports `MMPoseInferencer` default model and ignores local weights | NO | COCO-17 only if it ran | NO | Matching MMPose config files are missing; current adapter does not load checkpoints | Install OpenMMLab stack, add matching configs, implement explicit checkpoint/config loading |
| Person detector | YES weights | `models/tracking/rtmdet_nano...pth` 4.03 MB; `rtmdet_m...pth` 94.43 MB; `bytetrack_s_mot17.pth.tar` 68.51 MB; `yolov8x.pt` under WHAM 130.53 MB | `mmdet`/OpenMMLab and `ultralytics` missing | MISSING adapter; current `tracking/person.py` only checks single pose sequence coverage | NO | None | NO raw-frame detection | No multi-person detector or tracker integrated | Add detector abstraction after MVP MediaPipe; wire RTMDet-m or YOLO to pre-pose person box |
| Depth Anything V2 | YES | Small 94.62 MB; Base 371.9 MB; Large 1279.25 MB | `torch`, `transformers`, `depth_anything_v2` missing | MISSING | NO | None | NO | Optional scale/depth; no code path | Defer until pose/event MVP works |
| WHAM | PARTIAL weights | `wham_vit_w_3dpw.pth.tar` 502.88 MB; `wham_vit_bedlam_w_3dpw.pth.tar` 502.88 MB; `hmr2a.ckpt` 2583.97 MB; `dpvo.pth` 13.51 MB; `vitpose-h-multi-coco.pth` 2430.99 MB | `torch`, `wham`, `smplx`, `ultralytics` missing | MISSING | NO | None | NO | SMPL assets incomplete: no `SMPL_NEUTRAL.pkl`/male/female/basicModel assets found; only regressors/smplx2smpl/mean params | Defer; obtain legal SMPL/SMPLify assets and implement 3D adapter later |
| ViTPose extras | YES | Multiple `.pth` and one HF `model.safetensors`, largest 3551.45 MB | `torch`, `transformers` missing | MISSING | NO | None | NO | Not in requested MVP path | Defer |

## Model Loading System

| Component | Status | Notes |
| --- | --- | --- |
| `models/model_registry.py` | PARTIALLY IMPLEMENTED | Knows MediaPipe, MMPose, demo; `all_backend_names()` omits raw `mmpose` and returns `mmpose_future` |
| `models/model_loader.py` | PARTIALLY IMPLEMENTED | Enforces no real->demo fallback, but verify/healthcheck criteria are too weak for future real model success |
| `models/model_status.py` | VERIFIED PRESENT | Pydantic status schemas exist |
| `pipeline/pose/mediapipe_adapter.py` | BROKEN in current env | Uses `mediapipe.solutions.pose`, not Tasks `.task` files |
| `pipeline/pose/mmpose_adapter.py` | PLACEHOLDER/PARTIAL | Does not load local weights/configs; deps missing |
| `pipeline/segmentation/sam2_adapter.py` | PLACEHOLDER ONLY | `segment_person` raises `NotImplementedError` |
| WHAM adapter | MISSING | No adapter |
| Depth adapter | MISSING | No adapter |

## Model Setup Scripts

| Script | Exists | Imports correctly | Verifies real inference | Downloads/checks weights | Missing handling | Non-zero on failure | Current result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `scripts/download_models.py` | YES | YES | NO, only MediaPipe availability check | Does not download current large weights; creates dirs | YES | NO, returns 0 even if MediaPipe nonfunctional | Ran; MediaPipe functional NO |
| `scripts/verify_models.py` | YES | YES | PARTIAL | No weight download | YES | YES | Ran; FAILED due `mediapipe.solutions` missing |
| `scripts/model_healthcheck.py` | YES | YES | PARTIAL | No | YES | YES | Ran; FAILED at backend resolution |
| `scripts/test_pose_on_sample_video.py` | YES | Inspected | Would run estimator and write outputs | No | YES | YES on model unavailable | Not run: no real sample and script writes extra JSON/PNG/report artifacts |
| `apps/api/scripts/smoke_test.py` | YES | YES | Demo only | No | N/A | Assertions | Ran; PASSED demo presets |
| `apps/api/scripts/integration_test.py` | YES | YES | Endpoint/control-plane | No | YES | Assertions | Ran against temporary server; PASSED |

Scripts that should be created or revised:

- `scripts/verify_mediapipe_tasks.py`: initialize each `.task` file, run one real frame if available, require at least 33 landmarks on a real sample.
- `scripts/model_inventory.py`: compare expected filenames/configs/deps against local state.
- `scripts/verify_mmpose.py`: require config + checkpoint + detector + a real sample frame.
- `scripts/verify_segmentation.py`: only after SAM2 adapter exists.

## Demo Pipeline

Status: **VERIFIED WORKING**

Evidence:

- Smoke script completed `normal`, `asymmetric`, `poor_quality`, and `tug`.
- HTTP integration completed demo analysis.
- Demo output included 15 metrics, 17 keypoint stats, pose track, model-status, valid PDF.
- Demo metrics are computed from simulated keypoints, not hardcoded report numbers.

Limitations:

- Demo is simulated and must remain clearly separated from real patient analysis.
- Demo video generation produced OpenH264 warnings in this Windows environment.
- Server-side overlay MP4 demo warning is likely missing due the `analysis_mode.value == "demo"` bug.

## Real Model Pipeline

Status: **BROKEN for current app**

What exists:

- `model_loader.get_real_estimator()` never returns simulated data.
- `analysis/start` gates real analysis on model status and returns 422 if unavailable.
- Orchestrator has a real path that would decode frames and call `estimator.estimate_2d_pose`.
- Metrics can consume any valid `PoseSequence`.

What is blocked:

- Current MediaPipe adapter cannot initialize because `mediapipe.solutions.pose` is absent.
- Current adapter ignores local `.task` files.
- No real sample video exists to prove uploaded-video inference.

What is promising:

- `PoseLandmarker` from `mediapipe.tasks` is importable.
- Local `pose_landmarker_full.task` initialized and inference ran in a manual probe.

## Pose Adapters

| Adapter | Classification | Evidence |
| --- | --- | --- |
| Simulated | VERIFIED WORKING | Demo smoke and HTTP integration pass |
| MediaPipe Solutions adapter | BROKEN | Import check fails on `mediapipe.solutions` |
| MediaPipe Tasks adapter | MISSING | Runtime and weights exist, but no app adapter |
| MMPose adapter | PLACEHOLDER/PARTIAL | Uses default `MMPoseInferencer`; deps/configs missing; local weights ignored |
| SAM2 segmenter | PLACEHOLDER ONLY | `NotImplementedError` |
| WHAM / Depth | MISSING | No adapters |

## Gait Events

Status: **PARTIALLY IMPLEMENTED**

`pipeline/events.py` implements a Zeni-like coordinate method using ankle position relative to pelvis. It works on demo data and produces heel-strike/toe-off events.

Limitations:

- It uses ankles only, even when MediaPipe extra heel/foot_index keypoints are available in `PoseSequence`.
- It does not use SAM masks, foot segmentation, 3D depth, or WHAM.
- Event confidence is the ankle confidence only.

## Gait Metrics and Confidence

Status: **PARTIALLY IMPLEMENTED, computed for demo**

Metric schema supports:

- `value`
- `unit`
- `confidence`
- `source_keypoints`
- `source_model`
- `analysis_mode`
- `limitations`
- `confidence_reason`

The orchestrator refines metric confidence using:

- source keypoint confidence
- valid frame coverage
- interpolated frames
- video quality
- event consistency
- calibration availability
- camera view limitations

Per-metric audit:

| Metric | Status | Confidence/provenance status | Notes |
| --- | --- | --- | --- |
| Cadence | VERIFIED WORKING for demo | Refined from ankle/heel keypoint stats and event consistency | Real blocked |
| Step count | VERIFIED WORKING for demo | Refined | Counts detected events; limited by short clips |
| Left/right step time | VERIFIED WORKING for demo | Refined | Uses detected heel strikes |
| Stride time | VERIFIED WORKING for demo | Refined | Uses same-foot event intervals |
| Asymmetry | VERIFIED WORKING for demo | Asymmetry model lacks full per-metric source fields | Computed for step time, stride time, ROM |
| Walking speed | PARTIAL | Confidence downgraded if uncalibrated | Uses calibration distance or height estimate; not true calibrated unless input exists |
| Hip ROM | PARTIAL | Refined from hip/knee/shoulder | 2D camera-dependent approximation |
| Knee ROM | PARTIAL | Refined from hip/knee/ankle | 2D camera-dependent approximation |
| Ankle ROM | MISSING | N/A | Not implemented |
| Trunk sway | PARTIAL | Refined from shoulders/nose | 2D trunk tilt variability, not clinical balance measure |
| Mobility Risk Support Score | PARTIAL/WORKING for demo | Overall confidence from metric bundle | Screening aid only, not validated |
| TUG metrics | PARTIAL/MISSING | N/A | TUG preset and labels exist; no phase timing, sit/stand, turn-time, total TUG-specific extraction |

Known confidence issue:

- `model_loader.verify()` and `healthcheck()` need stricter landmark requirements. They should not pass just because inference ran on blank/synthetic frames.

## Keypoint Analysis UI

Status: **VERIFIED PRESENT and builds**

| Item | Classification | Evidence |
| --- | --- | --- |
| Keypoint Analysis tab | VERIFIED WORKING by build | `results-view.tsx` tab state includes `keypoints` |
| Video/canvas skeleton overlay | VERIFIED PRESENT | `skeleton-canvas.tsx` draws video + canvas |
| Per-keypoint rendering | VERIFIED PRESENT | Loops all `frame.keypoints` |
| Confidence colors | VERIFIED PRESENT | `confidenceColor` from shared helper |
| Color legend | VERIFIED PRESENT | `KEYPOINT_LEGEND` rendered |
| Toggles tracking confidence / movement flags / both / hide colors | VERIFIED PRESENT | `COLOR_MODES` in keypoint component |
| Clickable keypoints | VERIFIED PRESENT | Canvas click selects nearest keypoint |
| Hoverable keypoints | MISSING | No hover handler/tooltip |
| Details panel | VERIFIED PRESENT | Shows side, avg confidence, valid/missing/interpolated, related metrics |
| Keypoint confidence chart | VERIFIED PRESENT | Recharts area chart |
| Missing frame percentage | VERIFIED PRESENT | From `KeypointStat` |
| Left/right leg tracking quality | VERIFIED PRESENT | Computes from hip/knee/ankle/heel/foot_index stats |
| Gait event markers | VERIFIED PRESENT | Timeline markers and nearby event label |
| Patient-visible disclaimer | VERIFIED PRESENT | Shared `KEYPOINT_COLOR_DISCLAIMER` |

## JSON, PDF, Overlay

| Export | Status | Notes |
| --- | --- | --- |
| JSON report | VERIFIED WORKING for demo | `/analysis/{id}/report.json` returns full result schema |
| PDF report | VERIFIED WORKING for demo | HTTP integration returned valid `%PDF` bytes; includes model transparency and disclaimer |
| Frontend report page | VERIFIED BY BUILD | Renders result, case info, metrics, flags, model metadata |
| Server overlay video | PARTIAL | Route and renderer exist; not HTTP-tested in this audit; demo warning bug exists |
| Interactive overlay UI | VERIFIED BY BUILD | Frontend canvas overlay from pose track |

PDF limitation: it includes model transparency but does not show every metric's `source_keypoints`, `source_model`, and `confidence_reason` in the metric table.

## Docker and Dependency Packaging

Status: **PARTIALLY IMPLEMENTED**

- `apps/api/Dockerfile` installs `requirements.txt`.
- `requirements.txt` does not install MediaPipe by default; it only comments optional `mediapipe`.
- Therefore the Docker API container will not have real pose inference unless dependency installation is changed.
- `docker-compose.yml` sets `HORALIX_POSE_BACKEND=auto`, but with the current Dockerfile this will not make real analysis work.
- Web Dockerfile is standard Next.js build/start.

## Test Coverage

Status: **PARTIAL**

What exists:

- `apps/api/scripts/smoke_test.py`: demo pipeline smoke test. Passed.
- `apps/api/scripts/integration_test.py`: HTTP integration against running API. Passed for demo/export/model-status/real-fail-fast.
- `scripts/verify_models.py`: model verification. Failed currently.
- `scripts/model_healthcheck.py`: model healthcheck. Failed currently.
- Frontend production build. Passed.

What is missing:

- No `apps/api/tests` unit/integration test files.
- No pytest suite.
- No frontend unit tests.
- No Playwright or browser screenshot checks.
- No real-video golden sample test.
- No CI evidence in this audit.

## Security and Medical Safety

| Item | Classification | Evidence / gap |
| --- | --- | --- |
| Non-diagnostic disclaimer | VERIFIED PRESENT | UI/PDF/narrative/docs |
| Clinician review wording | VERIFIED PRESENT | UI/report/narrative/docs |
| Real vs demo warning | PARTIAL | Result/PDF/UI work; server overlay bug; wording still says fallback |
| Patient privacy note | PARTIAL | De-identified patient code guidance; no auth/access control |
| Video deletion capability | PARTIAL | `DELETE /videos/{id}` deletes raw file only, retains analysis artifacts |
| No unnecessary full names | PARTIAL | UI asks patient code/initials; clinician free-text field exists |
| Audit metadata | PARTIAL | Analysis id, created_at, model_info, pipeline version; no user audit log |
| Model provenance | VERIFIED PRESENT for result/PDF/UI | `ModelInfo` stored and shown |
| Known limitations | VERIFIED PRESENT | Result limitations/docs |
| Clinical validation status | PARTIAL | ModelInfo says validation required/not clinical grade; no validation data |
| Regulatory warning | PARTIAL | Docs state not medical device; app disclaimer shorter |
| Access control | MISSING | No auth/roles |
| Encryption/retention policy | MISSING | Local files only; no retention jobs |

## Broken, Placeholder, or Stale Code

Critical:

- **BROKEN:** MediaPipe app adapter uses `mediapipe.solutions.pose`; installed package lacks `mediapipe.solutions`.
- **MISSING:** MediaPipe Tasks adapter using `.task` model files.
- **BROKEN:** Real uploaded-video analysis cannot run in current environment.
- **MISSING:** Real sample video for verification.

Important:

- **PLACEHOLDER:** SAM2 adapter.
- **PLACEHOLDER/PARTIAL:** MMPose adapter.
- **MISSING:** Depth Anything adapter.
- **MISSING:** WHAM/SMPL adapter.
- **MISSING/PARTIAL:** Raw-frame person detector/tracker integration.
- **PARTIAL:** MMPose/RTMW matching config files absent.
- **MISSING:** SMPL body model assets.
- **PARTIAL:** Event detector does not use heel/toe extra keypoints.
- **PARTIAL:** No ankle ROM and no real TUG phase metrics.
- **BROKEN/PARTIAL:** Server overlay demo label check uses `"demo"` instead of `demo_simulated`.
- **PARTIAL:** `model_loader.verify()` can pass without landmarks if real inference runs.
- **PARTIAL:** `model_loader.status().real_analysis_available` can be inconsistent with configured backend.
- **STALE:** `pipeline/pose/factory.py` and docs describe fallback behavior that the active orchestrator no longer uses.
- **PARTIAL:** Docker backend image does not install MediaPipe or heavy runtime deps.

## Recommended Model Folder Structure

Use this target structure for implementation, even though current local weights are under root `models/`:

```text
apps/api/models/
  mediapipe/
    pose_landmarker_full.task
    pose_landmarker_heavy.task
  sam2/
    sam2.1_hiera_tiny.pt
  mmpose/
    rtmw/
      rtmw-x_384x288.pth
      rtmw-x_384x288.py
    rtmw3d/
    rtmpose/
    detectors/
      rtmdet_m_person.pth
      rtmdet_m_person.py
  depth_anything/
    depth_anything_v2_vitl.pth
  wham/
    checkpoints/
    smpl/
```

Priority:

1. **MediaPipe Pose Landmarker Full**: required for MVP. Current weights and Tasks runtime exist; implement first.
2. **MediaPipe Pose Landmarker Heavy**: optional quality upgrade after Full works.
3. **SAM2.1 Tiny**: optional segmentation/masking; not required for MVP gait metrics.
4. **RTMW-X 384x288 + RTMDet-m detector**: high-accuracy 2D whole-body path; requires OpenMMLab deps/configs.
5. **RTMW3D-X**: research 3D path; defer until 2D path stable.
6. **Depth Anything V2 Large**: optional scale/depth; heavy and not first implementation.
7. **WHAM + SMPL/SMPLify**: too heavy for first implementation; missing legal SMPL assets and runtime.

## Exact Next Engineering Milestone

Implement and verify a real **MediaPipe Tasks PoseLandmarker** backend as the MVP real model path.

Acceptance criteria:

1. Adapter loads `models/pose/mediapipe/pose_landmarker_full.task` or configured path.
2. Adapter initializes `mediapipe.tasks.python.vision.PoseLandmarker`.
3. Adapter processes actual decoded video frames.
4. Adapter maps landmarks to `PoseSequence` with COCO-17 + heel/foot_index extras.
5. `scripts/verify_models.py` fails unless inference runs and landmarks are detected on a real sample video.
6. `scripts/model_healthcheck.py` fails unless valid landmarks exist.
7. `POST /analysis/start` on a real uploaded walking clip completes with `analysis_mode=real_mediapipe`, `simulated_data_used=false`.
8. Frontend, JSON, PDF, and model-status show real provenance.
9. Demo remains explicit and never contaminates real analysis.
10. Add one small sample/golden test path or documented local sample requirement.

