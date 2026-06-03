# Sample videos — required for FULL REAL verification

Place a **real human walking** clip here:

```
data/sample_videos/walk_test.mp4
```

Then run (real backend must be installed — see README "Real AI Vision Setup"):

```
python scripts/test_pose_on_sample_video.py
python scripts/test_real_upload_flow.py http://127.0.0.1:8010
```

## Recording requirements

- A real human walking (not an animation or drawing)
- Side view preferred (sagittal)
- Full body visible head-to-feet for the whole clip
- Feet clearly visible
- Stable camera (tripod / fixed surface)
- Good, even lighting
- 30 fps preferred
- 5–15 seconds
- Person walks naturally across the frame
- Only one person in frame

## Why it is required

MediaPipe Pose detects landmarks on **real humans**; it returns no landmarks on
synthetic frames. Without this file the pipeline can only be verified in
**MODEL EXECUTION VERIFIED ONLY** mode (model loads, initializes, runs inference)
— it cannot reach **FULL REAL VERIFIED** (real landmarks → metrics) and the
verification scripts will say so honestly.
