"""Run the REAL pose model on a sample video (or a generated test clip).

    python scripts/test_pose_on_sample_video.py

Prefers data/sample_videos/walk_test.mp4 (a real person). If absent, generates a
simple synthetic clip that only verifies model EXECUTION (not clinical gait
performance). Saves keypoints, an overlay preview and a test report.
"""
from __future__ import annotations

import json

import numpy as np

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
OUT_DIR = REPO_ROOT / "data" / "processed"


def _synthetic_clip(n: int = 40, h: int = 480, w: int = 640) -> np.ndarray:
    import cv2

    frames = np.empty((n, h, w, 3), np.uint8)
    for i in range(n):
        img = np.full((h, w, 3), 60, np.uint8)
        cx = int(w * (0.3 + 0.4 * i / n))
        leg = 18 + int(10 * np.sin(i / 3))
        cv2.circle(img, (cx, 90), 32, (220, 200, 180), -1)
        cv2.rectangle(img, (cx - 32, 122), (cx + 32, 300), (200, 180, 160), -1)
        cv2.rectangle(img, (cx - leg, 300), (cx - 6, 450), (190, 170, 150), -1)
        cv2.rectangle(img, (cx + 6, 300), (cx + leg, 450), (190, 170, 150), -1)
        frames[i] = img
    return frames


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from app.models.model_loader import ModelUnavailableError, get_model_loader

    try:
        estimator, mode = get_model_loader().get_real_estimator()
    except ModelUnavailableError as e:
        print(f"Cannot run real model: {e}")
        print("Install MediaPipe and re-run: pip install mediapipe")
        return 1

    import cv2

    from app.pipeline.pose.base import SKELETON_EDGES

    if SAMPLE.exists():
        from app.pipeline.video_processor import VideoProcessor

        decoded = VideoProcessor(max_frames=300).load(SAMPLE, min_seconds=0.2)
        frames, fps = decoded.frames, decoded.fps
        source = str(SAMPLE)
        synthetic = False
    else:
        frames, fps = _synthetic_clip(), 30.0
        source = "generated_synthetic"
        synthetic = True
        print("No real walking sample video found. Generated test video only "
              "verifies model execution, not clinical gait performance.")

    seq = estimator.estimate_2d_pose(frames, fps)
    kps = seq.all_keypoints()
    scores = kps[..., 2]
    valid = int(np.sum(np.nanmean(scores, axis=1) > 0.3))
    avg_conf = float(np.nanmean(scores)) if scores.size else 0.0

    # Save keypoints.
    kp_path = OUT_DIR / "sample_keypoints.json"
    kp_path.write_text(json.dumps({
        "source": source, "synthetic": synthetic, "fps": fps,
        "keypoint_names": seq.all_names(),
        "frames": [
            {"t": round(float(seq.timestamps[i]), 3),
             "keypoints": [[round(float(x), 1), round(float(y), 1), round(float(s), 3)]
                           for x, y, s in kps[i]]}
            for i in range(seq.num_frames)
        ],
    }), encoding="utf-8")

    # Overlay preview PNGs.
    preview_paths = []
    for j, i in enumerate(np.linspace(0, seq.num_frames - 1, min(6, seq.num_frames)).astype(int)):
        img = frames[i].copy()
        for a, b in SKELETON_EDGES:
            pa, pb = kps[i, a], kps[i, b]
            if pa[2] > 0.2 and pb[2] > 0.2:
                cv2.line(img, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])),
                         (60, 200, 90), 2)
        p = OUT_DIR / f"sample_overlay_{j:02d}.png"
        cv2.imwrite(str(p), img)
        preview_paths.append(str(p))

    report = {
        "backend": mode.value,
        "model": estimator.get_model_info().name,
        "source": source,
        "synthetic": synthetic,
        "frames_processed": seq.num_frames,
        "valid_pose_frames": valid,
        "failed_frames": seq.num_frames - valid,
        "average_confidence": round(avg_conf, 3),
        "outputs": {"keypoints": str(kp_path), "overlay_previews": preview_paths},
    }
    (OUT_DIR / "model_test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== pose-on-sample-video ===")
    for k in ("backend", "model", "source", "frames_processed", "valid_pose_frames",
              "failed_frames", "average_confidence"):
        print(f"  {k}: {report[k]}")
    print(f"  keypoints: {kp_path}")
    print(f"  overlay previews: {len(preview_paths)} PNG(s) in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
