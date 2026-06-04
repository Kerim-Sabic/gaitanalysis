# Manual acceptance test

Final human walkthrough before a demo. Automated suites cover backend, exports
and contracts; this confirms the webcam and end-to-end UX.

## A. Local app
- [ ] Backend starts (`uvicorn app.main:app --port 8010`).
- [ ] Frontend starts (`npm run dev`), landing page loads.
- [ ] API status indicator shows "connected".

## B. Live tracking (`/live-analysis`)
- [ ] Camera permission granted; feed visible.
- [ ] Skeleton appears on the person.
- [ ] Keypoint confidence colours change with movement.
- [ ] Capture coaching updates.
- [ ] FPS + inference time visible.
- [ ] Real backend shown; `simulated_data_used = false`.

## C. Record / upload
- [ ] Record 10 seconds walking sideways.
- [ ] Upload starts and analysis completes.
- [ ] Selected backend shown (MediaPipe Heavy/Full).
- [ ] Keypoint overlay visible on result.
- [ ] Gait events visible.
- [ ] Metrics visible (cadence, step/stride timing, asymmetry, ROM).
- [ ] Report visible.

## D. Exports
- [ ] PDF downloads and opens.
- [ ] JSON downloads.
- [ ] Disclaimer present in report.

## E. Failure cases
- [ ] Backend offline → clean message.
- [ ] Camera denied → clean message.
- [ ] Poor/short video → quality warning, not a crash.
- [ ] Demo mode clearly labelled "simulated — not patient analysis".

Mark complete when all boxes pass: **MANUAL ACCEPTANCE READY**.
