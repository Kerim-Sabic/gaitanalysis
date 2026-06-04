# Deployment

## Architecture

Horalix Gait AI uses two separately deployed services:

- **Netlify:** the Next.js frontend in `apps/web`
- **External host:** the FastAPI, MediaPipe, OpenCV, reports, and model files in
  `apps/api`

Netlify must not run the Python vision pipeline in Functions. The browser calls
the external backend directly through `NEXT_PUBLIC_API_URL`.

## Netlify Frontend

Deploy branch: `feature/netlify-frontend-deploy`

The root `netlify.toml` defines the verified settings:

| Setting | Value |
| --- | --- |
| Base directory | `apps/web` |
| Build command | `npm ci --no-audit --no-fund && npm run build` |
| Publish directory | `.next` |
| Node version | `20` |

Set this environment variable for production and deploy previews:

```text
NEXT_PUBLIC_API_URL=https://your-fastapi-backend-domain.com
```

Do not include a trailing slash. Netlify provides HTTPS, which is required for
browser camera access on `/live-analysis`. Custom domains also need HTTPS.
Deploy previews need access to a backend whose CORS list includes the preview
domain, or they should be treated as frontend-only previews.

## FastAPI Backend

Python 3.11 is recommended. Render, Railway, or Fly.io are practical demo hosts.
A VPS such as Hetzner or an AWS service gives more control. Use a GPU host later
for MMPose, TensorRT, or other heavy models.

Install and start from `apps/api`:

```bash
python -m pip install -r requirements-real.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required backend environment:

```text
HORALIX_POSE_BACKEND=auto_best
HORALIX_AUTO_BEST_MODE=fast
HORALIX_LIVE_BACKEND=mediapipe_tasks_full
HORALIX_FINAL_BACKEND=auto_best
HORALIX_CORS_ORIGINS=https://YOUR-NETLIFY-SITE.netlify.app,https://YOUR-CUSTOM-DOMAIN.com
```

For local development:

```text
HORALIX_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Do not use wildcard CORS in production. The backend needs these local model
files or mounted equivalents:

- `pose_landmarker_full.task`
- `pose_landmarker_heavy.task`
- optional `yolov8n-pose.pt`

Uploaded videos, generated reports, and the SQLite database use local disk.
Production deployments need persistent disk or an object-storage/database
implementation; ephemeral host files can disappear on restart or redeploy.

## Live Analysis

The browser may record WebM depending on codec support. The backend must decode
WebM or return a structured `video_invalid`/unsupported-format error. The
frontend shows a readable codec message instead of claiming analysis succeeded.

The external backend must expose and allow CORS access to:

- `GET /health`
- `GET /models/status`
- `GET /live/status`
- `POST /live/frame`
- video upload, analysis, report, and media endpoints

## Production Safety

- This system is not clinically validated and is not a standalone diagnosis.
- De-identify patient videos and metadata before upload.
- Use HTTPS for both frontend and backend.
- Protect upload/report storage and define retention/deletion policies.
- Delete demonstration uploads when they are no longer needed.
- Keep model weights and generated patient artifacts out of Git.

## Verification

```bash
python scripts/check_netlify_frontend.py
cd apps/web
npm run build
```

With a local backend running on port `8010`:

```powershell
apps/api/.venv/Scripts/python.exe scripts/release_check.py --api http://127.0.0.1:8010 --full --strict
```
