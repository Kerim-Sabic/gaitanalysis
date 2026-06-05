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
POST /live/frame            (multipart image → real keypoints)
# upload → full analysis → /analysis/{id}/result, /report.pdf, /report.json
```

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

## H. Safety / privacy
- Outputs are for clinician review; not a standalone diagnosis; not clinically validated.
- De-identify subjects (use patient codes/initials; no full names).
- HTTPS required on both frontend and backend.
- Define an uploaded-video storage + deletion/retention policy before production use.
- CORS must list only the real frontend origins (no wildcard in production).
