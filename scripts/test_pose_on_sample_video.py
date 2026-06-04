"""Run the REAL configured pose backend on the sample walking video.

    python scripts/test_pose_on_sample_video.py

Requires data/sample_videos/walk_test.mp4 (a real person walking). Writes:
  data/processed/model_tests/sample_keypoints.json
  data/processed/model_tests/model_test_report.json
  data/processed/model_tests/sample_overlay_*.png

Statuses: FULL REAL VERIFIED (valid frames>0) | FAILED (0 valid frames) |
SAMPLE MISSING. Never fakes success.
"""
from __future__ import annotations

import json

import numpy as np

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
OUT = REPO_ROOT / "data" / "processed" / "model_tests"


def main() -> int:
    from app.models.model_loader import ModelUnavailableError, get_model_loader

    try:
        estimator, mode = get_model_loader().get_real_estimator()
    except ModelUnavailableError as e:
        print(f"Cannot run real model: {e}")
        print("Fix: pip install mediapipe  (ensure .task under models/pose/mediapipe/)")
        return 1

    if not SAMPLE.exists():
        print("No real walking sample video found. Full real gait verification cannot be "
              f"performed.\nPlace a real walking clip at: {SAMPLE}")
        print("STATUS: SAMPLE MISSING")
        return 0

    import cv2

    from app.pipeline.pose.base import SKELETON_EDGES
    from app.pipeline.video_processor import VideoProcessor

    OUT.mkdir(parents=True, exist_ok=True)
    decoded = VideoProcessor(max_frames=300).load(SAMPLE, min_seconds=0.5)
    seq = estimator.estimate_2d_pose(decoded.frames, decoded.fps)
    kps = seq.all_keypoints()
    scores = kps[..., 2]
    valid = int(np.sum(np.nanmean(scores, axis=1) > 0.3))
    avg_conf = float(np.nanmean(scores)) if scores.size else 0.0

    kp_path = OUT / "sample_keypoints.json"
    kp_path.write_text(json.dumps({
        "backend": mode.value, "fps": decoded.fps, "keypoint_names": seq.all_names(),
        "frames": [
            {"t": round(float(seq.timestamps[i]), 3),
             "keypoints": [[round(float(x), 1), round(float(y), 1), round(float(s), 3)]
                           for x, y, s in kps[i]]}
            for i in range(seq.num_frames)
        ],
    }), encoding="utf-8")

    previews = []
    for j, i in enumerate(np.linspace(0, seq.num_frames - 1, min(6, seq.num_frames)).astype(int)):
        img = decoded.frames[i].copy()
        for a, b in SKELETON_EDGES:
            pa, pb = kps[i, a], kps[i, b]
            if pa[2] > 0.2 and pb[2] > 0.2:
                cv2.line(img, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), (60, 200, 90), 2)
        p = OUT / f"sample_overlay_{j:02d}.png"
        cv2.imwrite(str(p), img)
        previews.append(str(p))

    report = {
        "backend": mode.value, "model": estimator.get_model_info().name,
        "model_file": getattr(estimator, "model_file", ""), "source": str(SAMPLE),
        "frames_processed": seq.num_frames, "valid_pose_frames": valid,
        "failed_frames": seq.num_frames - valid, "average_confidence": round(avg_conf, 3),
        "landmark_count": int(kps.shape[1]), "outputs": {"keypoints": str(kp_path),
                                                         "overlay_previews": previews},
    }
    (OUT / "model_test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== pose-on-sample-video ===")
    for k in ("backend", "model", "frames_processed", "valid_pose_frames", "failed_frames",
              "average_confidence", "landmark_count"):
        print(f"  {k}: {report[k]}")
    print(f"  outputs: {kp_path}  + {len(previews)} overlay PNG(s)")

    if valid == 0:
        print("STATUS: FAILED (zero valid pose frames — check framing/quality)")
        return 1
    print("STATUS: FULL REAL VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
