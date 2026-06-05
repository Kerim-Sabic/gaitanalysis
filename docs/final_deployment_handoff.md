# Final Deployment Handoff — Horalix Gait AI

> AI-assisted gait quantification for clinician review. **Not a standalone
> diagnostic decision; not clinically validated; not a medical device.**

## A. Final verified branch
`feature/actual-advanced-model-runtime` (commit `89ccd03` + handoff doc commit).

Verified locally: `final_done_app_check --api --full` → DONE APP VERIFIED ·
`release_check --strict` → RELEASE-CANDIDATE VERIFIED · `clinical_demo_check` →
VERIFIED · `npm run build` → PASS · reliability → VERIFIED.

## B. Frontend deployment (Netlify)
- Base directory: `apps/web`
- Build command: `npm install && npm run build`
- Publish directory: `.next` (Netlify Next.js runtime)
- Environment:
  - `NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-DOMAIN`  (no trailing slash; HTTPS)
- Netlify provides HTTPS, which the browser requires for `/live-analysis` camera.

## C. Backend deployment (FastAPI — separate host, NOT Netlify)
- Python 3.11 recommended.
- Install: `python -m pip install -r apps/api/requirements-real.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Place the required model files (Section E) on the host (not committed).

## D. Backend environment variables
```
HORALIX_POSE_BACKEND=auto_best
HORALIX_AUTO_BEST_MODE=fast
HORALIX_LIVE_BACKEND=mediapipe_tasks_full
HORALIX_ENABLE_SAM2=true
HORALIX_ENABLE_DEPTH=true
HORALIX_CORS_ORIGINS=https://YOUR-NETLIFY-SITE.netlify.app,https://YOUR-CUSTOM-DOMAIN.com
```

## E. Required models on the backend (git-ignored; provide at deploy)
- `models/pose/mediapipe/pose_landmarker_full.task`
- `models/pose/mediapipe/pose_landmarker_heavy.task`
- `models/pose/ultralytics/yolov8n-pose.pt`
- `models/segmentation/sam2.1_hiera_tiny.pt` (helper, if `HORALIX_ENABLE_SAM2=true`)
- `models/depth/Depth-Anything-V2-Small/...` or configured `HORALIX_DEPTH_MODEL_PATH`

## F. Optional advanced models
- **MMPose RTMW**: not runnable on bare Windows (`mmcv._ext` compiled ops missing).
  Use Docker: `docker compose --profile mmpose up --build api-mmpose`.
- **MMPose RTMW3D**: `BLOCKED_CONFIG` — needs matching config + verified 3D mapping.
- **WHAM**: `BLOCKED_LICENSED_ASSETS` — requires licensed `SMPL_NEUTRAL.pkl` from
  <https://smpl.is.tue.mpg.de> at `models/body_models/smpl/` (never auto-downloaded).
- **SAM2 / Depth Anything V2**: runtime verified; enable via the env flags above.

## G. Post-deployment verification
```
GET  /health
GET  /live/status
GET  /models/status
GET  /models/capabilities   (live model cards for the setup flow)
POST /analysis/preflight    (resolve setup → plan / blocked reasons)
POST /live/frame            (multipart image → real keypoints)
# upload → full analysis → /analysis/{id}/result, /report.pdf, /report.json
```

## G0. Pre-analysis model selection (no env vars required)
Users pick models in the UI at `/analysis/setup`: capture source → protocol →
analysis quality → model cards → calibration → review. Model availability is read
live from `GET /models/capabilities` (the frontend never hardcodes status).

- **Standard** — fast real pose only (inherits server helper defaults).
- **Advanced Clinical** — turns on SAM2 + Depth **when installed**, per request.
- **Expert** — pin a pose backend, toggle helpers, and require them (fail instead
  of degrade) via `require_selected_pose_backend` / `require_advanced_helpers`.

The selection is sent as `options` on `POST /analysis/start` and is honored by the
pipeline **per request** — Advanced Clinical activates SAM2/Depth without setting
`HORALIX_ENABLE_*`. Phone capture inherits the setup: the desktop passes `options`
to `POST /mobile/session` and the phone clip runs with the same selection. Each
result records requested-vs-actual provenance (`model_info.analysis_request` /
`model_info.model_execution`), shown in the UI, JSON, and PDF.

Local helper scripts: `scripts/run_api_advanced.ps1` (API with SAM2+Depth runtime)
and `scripts/run_web_local_phone.ps1` (web on the LAN for phone QR). Verify with
`scripts/test_analysis_setup_preflight.py` and `scripts/test_advanced_mode_request.py`.

## G2. QR phone-capture deployment
- Desktop creates a pairing session (`POST /mobile/session`); the phone opens
  `/<frontend>/mobile-capture/{session}?token=...` (from the QR), records/uploads,
  and the clip runs the same verified analysis. Desktop polls and opens the report.
- **HTTPS is required** on the frontend for phone camera access (Netlify provides it);
  the backend should also be HTTPS and reachable from phones.
- Set `NEXT_PUBLIC_APP_URL` to the public frontend origin if the QR must encode a
  domain different from the browser origin (otherwise `window.location.origin` is used).
- `HORALIX_CORS_ORIGINS` must include the frontend origin so phone uploads pass CORS.
- Mobile browser requirements: a modern Chrome/Safari with `getUserMedia` +
  `MediaRecorder`; camera permission must be granted. Gallery upload is the fallback.
- Backend upload limit is 400 MB per clip; sessions expire after 15 minutes and are
  single-use.
- **Multi-worker production**: the session store is in-memory (single worker). For
  multiple backend instances/workers, back it with Redis or a database so any worker
  can resolve a session.

## G3. Advanced single-runtime: SAM2 + Depth ACTIVE in real analysis
By default the app runs MediaPipe + Ultralytics (lightweight). To make **SAM2**
segmentation and **Depth Anything V2** *active in real analysis* (not just verified),
install all required deps into ONE venv and enable them:

```powershell
cd apps/api
python -m venv .venv ; .venv\Scripts\activate
python -m pip install -r requirements-real.txt        # MediaPipe + Ultralytics + core
python -m pip install -r requirements-depth.txt        # Depth Anything V2 (torch + transformers)
python -m pip install -r requirements-sam2.txt         # official SAM2 (needs torch); pulls hydra-core, iopath
# run with helpers enabled:
$env:HORALIX_POSE_BACKEND="auto_best"; $env:HORALIX_AUTO_BEST_MODE="fast"
$env:HORALIX_ENABLE_SAM2="true"; $env:HORALIX_SEGMENTATION_BACKEND="sam2"
$env:HORALIX_ENABLE_DEPTH="true"; $env:HORALIX_DEPTH_BACKEND="depth_anything_v2"
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Then real analysis reports `sam2_status=WORKING`, `depth_status=WORKING`,
`helper_models.sam2.used_in_analysis=true`, with masks/area/feet metadata folded
into capture quality (shown in UI, JSON, and PDF). Set `HORALIX_REQUIRE_SAM2=true`
(or `HORALIX_REQUIRE_DEPTH=true`) to make analysis FAIL (`sam2_required_but_unavailable`)
rather than degrade if a required helper is not active. Verify with
`scripts/test_real_advanced_analysis.py` and `scripts/diagnose_sam2_pipeline.py`.
SAM2's relative depth is **not** calibrated clinical distance.

## G4. Real-phone QR demo on the same Wi-Fi (no deploy)
A phone cannot reach `localhost` on the laptop. Run
`python scripts/print_local_network_urls.py` for your LAN IP + exact commands:

```powershell
# backend bound to all interfaces:
uvicorn app.main:app --host 0.0.0.0 --port 8010   # + HORALIX_CORS_ORIGINS=http://<LAN_IP>:3000
# frontend on the LAN IP:
$env:NEXT_PUBLIC_API_URL="http://<LAN_IP>:8010"; $env:NEXT_PUBLIC_APP_URL="http://<LAN_IP>:3000"
npm run dev -- --hostname 0.0.0.0
```

The desktop QR page warns when the encoded URL is `localhost` and shows the
backend URL. For phones requiring HTTPS camera access, use the deployed Netlify
frontend + a public HTTPS backend.

## H. Safety / privacy
- Outputs are for clinician review; not a standalone diagnosis; not clinically validated.
- De-identify subjects (use patient codes/initials; no full names).
- HTTPS required on both frontend and backend.
- Define an uploaded-video storage + deletion/retention policy before production use.
- CORS must list only the real frontend origins (no wildcard in production).
