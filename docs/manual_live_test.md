# Manual live-camera test

Automated tests cover the backend `/live/frame` contract but cannot exercise the
webcam. Run this once manually.

## Setup
- Backend: `cd apps/api && .venv\Scripts\activate && $env:HORALIX_POSE_BACKEND="auto_best"; uvicorn app.main:app --port 8010`
- Frontend: `cd apps/web` → set `NEXT_PUBLIC_API_URL=http://localhost:8010` in `.env.local` → `npm run dev`

## Checklist
1. Open <http://localhost:3000/live-analysis>.
2. Allow camera access (HTTPS or localhost required).
3. Stand with your full body in frame, side-on.
4. Confirm the **skeleton overlay** appears on you.
5. Confirm **keypoint colours change** as confidence changes when you move.
6. Confirm **feet / ankle** indicators appear when feet are visible.
7. Confirm **capture coaching** updates ("step back", "feet not visible", "good capture").
8. Confirm **FPS** and **inference time** are shown, and the badge reads
   "Live AI Preview — mediapipe_tasks_full" (real backend, `simulated_data_used=false`).
9. Press **Record 10s gait test** and walk sideways across the frame.
10. Confirm upload starts ("Processing…") and you are redirected to the analysis page.
11. Confirm the full analysis completes and the **report** opens with skeleton
    overlay, gait events, metrics, left/right comparison and model transparency.
12. Confirm **PDF** and **JSON** export.

## Failure cases to confirm
- Deny camera → clear "Camera access was denied" message + link to upload.
- Stop the backend → clear "backend offline/unreachable" message (no crash).
- Unset `NEXT_PUBLIC_API_URL` → clear "API not configured" message.

Mark complete when all steps pass: **MANUAL LIVE TEST READY**.
