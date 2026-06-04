# Deployment Handoff

## Verified Source

- Deployment branch: `feature/complete-app-verification`
- Verified commit before this handoff: `e47c37c`
- Frontend: `apps/web`
- Backend: `apps/api`

Deploy the frontend and backend as separate services. Do not run FastAPI,
MediaPipe, or OpenCV inside Netlify Functions.

## Frontend: Netlify

Import this repository into Netlify and deploy
`feature/complete-app-verification`.

| Setting | Value |
| --- | --- |
| Base directory | `apps/web` |
| Build command | `npm install && npm run build` |
| Publish directory | `.next` |
| Node version | `20` |

The repository's `netlify.toml` uses the reproducible equivalent
`npm ci --no-audit --no-fund && npm run build`.

Set this Netlify environment variable for production and deploy previews:

```text
NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-DOMAIN
```

The backend URL must be public, use HTTPS, and have no trailing slash. Netlify
provides the HTTPS origin required for browser camera access.

## Backend: External FastAPI Host

Run FastAPI on Render, Railway, Fly.io, a VPS, or another persistent Python
host. Python 3.11 is recommended.

Install and start from `apps/api`:

```bash
python -m pip install -r requirements-real.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set these backend environment variables:

```text
HORALIX_POSE_BACKEND=auto_best
HORALIX_AUTO_BEST_MODE=fast
HORALIX_LIVE_BACKEND=mediapipe_tasks_full
HORALIX_FINAL_BACKEND=auto_best
HORALIX_CORS_ORIGINS=https://YOUR-NETLIFY-SITE.netlify.app,https://YOUR-CUSTOM-DOMAIN.com
```

Do not use wildcard CORS in production. Add every production, custom, and
approved deploy-preview frontend origin that must call the backend.

## Required Backend Model Files

Mount or copy these files onto the backend host without committing them to Git:

- `pose_landmarker_full.task`
- `pose_landmarker_heavy.task`
- optional fallback: `yolov8n-pose.pt`

Use persistent storage for model files, uploaded videos, generated reports, and
the database. Ephemeral host storage can be deleted on restart or redeploy.

## Post-Deploy Verification

Verify the deployed backend:

1. `GET /health`
2. `GET /live/status`
3. `GET /models/status`
4. `POST /live/frame` with a decodable JPEG frame
5. Upload a de-identified walking video and run full analysis
6. Open the result and verify the selected real backend and model provenance
7. Download and open the PDF export
8. Download the JSON export

Then open the Netlify frontend:

1. Confirm the API status indicator shows connected.
2. Open `/live-analysis` and grant camera permission.
3. Confirm the skeleton, confidence colors, FPS, inference time, and capture
   coaching update.
4. Record a 10-second side-view walk and verify redirect to full analysis.
5. Confirm metrics, gait events, left/right comparison, joint ROM, model
   transparency, exports, and disclaimer.
6. Deny camera permission and stop the backend once to verify clean failure
   messages.

## Local Final Verification

Run from the repository root with the backend on port `8010`:

```powershell
apps/api/.venv/Scripts/python.exe scripts/final_done_app_check.py --api http://127.0.0.1:8010 --full
apps/api/.venv/Scripts/python.exe scripts/release_check.py --api http://127.0.0.1:8010 --full --strict
```

Run the physical webcam checklist in:

- `docs/manual_acceptance_test.md`
- `docs/manual_live_test.md`

Do not create `docs/manual_demo_pass_report.md` until a person has completed
every required physical webcam, recording, upload, result, and failure-state
check.

## Privacy And Clinical Safety

- De-identify all patient videos and metadata before upload.
- Require HTTPS for frontend and backend.
- Define access controls, retention, and deletion policies for uploaded videos
  and generated reports.
- Do not expose model files or storage paths publicly.
- Horalix Gait AI is not clinically validated and is not a standalone
  diagnostic system.
- Results are for clinician review only.
