# Manual phone-capture (QR) test

The backend session API + mobile route are covered by
`scripts/test_phone_capture_flow.py` (automated). This checklist covers the parts
that need a real phone + camera.

## Setup
- Backend: `cd apps/api && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8010`
  (use `0.0.0.0` so the phone can reach it; ensure `HORALIX_CORS_ORIGINS` includes the
  frontend origin).
- Frontend: `cd apps/web` → set `NEXT_PUBLIC_API_URL` (and optionally `NEXT_PUBLIC_APP_URL`)
  → `npm run dev`. Phone and desktop must be on the same network (or use the deployed
  Netlify URL + a public backend over HTTPS).

## Checklist
1. Open the desktop app → **Phone capture** (top nav) or landing "Use phone camera".
2. A QR card + short link + expiry countdown appears; status shows "Waiting for phone…".
3. Scan the QR with the phone camera.
4. The phone opens `/mobile-capture/<session>` and asks for camera permission.
5. Allow camera → live rear-camera preview shows.
6. Confirm the capture tips card is readable; record a 5–15 s sideways walking clip.
7. Preview the clip → tap **Upload & analyse**.
8. Phone shows "Upload complete — return to desktop".
9. Desktop status advances: phone connected → uploading → analysing → completes and
   **opens the result/report automatically**.
10. Export PDF and JSON from the result.

## Variations / failure cases
- **Gallery upload**: tap "Choose from gallery", pick a video → uploads + analyses.
- **Camera denied**: deny permission → page still offers "Choose from gallery" (no crash).
- **Backend offline**: stop backend → desktop shows a clean "offline/unreachable" status.
- **Expired QR**: wait > 15 min (or cancel) → desktop offers "New QR code".
- **Invalid/missing token**: opening the mobile URL without the token shows a clear message.

HTTPS is required for phone camera access on any non-localhost host (Netlify provides it).

Mark complete when all steps pass: **MANUAL PHONE CAPTURE READY**.
