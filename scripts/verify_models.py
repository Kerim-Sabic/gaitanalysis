"""Verify the configured real pose backend imports, initializes and runs inference.

    python scripts/verify_models.py

Full verification requires a real walking video at data/sample_videos/walk_test.mp4.
Without it, the model is exercised in EXECUTION-ONLY mode (no landmarks on
synthetic input) and the status reflects that — never a fake full pass.

Exit codes: 0 = passed or execution_only (model runs); 1 = failed (cannot run).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401


def main() -> int:
    from app.models.model_loader import SAMPLE_VIDEO, get_model_loader

    loader = get_model_loader()
    status = loader.status()
    res = loader.verify()

    print("=== Horalix model verification ===")
    print(f"Configured backend   : {status.configured_backend}")
    print(f"Model name           : {res.model_name or '(unresolved)'}")
    print(f"Model file           : {res.model_file or '-'}")
    print(f"Model version        : {res.model_version or '-'}")
    print(f"Device               : {res.device}")
    print(f"Sample used          : {res.sample_used}")
    print(f"Initialized          : {'yes' if res.initialized else 'no'}")
    print(f"Inference ran        : {'yes' if res.inference_ran else 'no'}")
    print(f"Frames processed     : {res.frames_processed}")
    print(f"Valid pose frames    : {res.valid_pose_frames}")
    print(f"Landmarks detected   : {'yes' if res.landmarks_detected else 'no'} "
          f"({res.landmark_count} keypoints/frame)")
    print(f"Average confidence   : {res.average_confidence:.3f}")
    if res.error:
        print(f"Error                : {res.error}")
    if res.note:
        print(f"Note                 : {res.note}")

    status_label = {
        "passed": "FULL REAL VERIFIED",
        "execution_only": "MODEL EXECUTION VERIFIED ONLY",
        "failed": "FAILED",
    }.get(res.status, res.status.upper())
    print(f"STATUS               : {status_label}")

    if res.status == "failed":
        print("\nReal pose model unavailable. Fix:")
        print("  pip install mediapipe   (and ensure a .task file under models/pose/mediapipe/)")
        print("  HORALIX_MEDIAPIPE_MODEL_PATH=<path-to>.task  to override the model path")
        return 1
    if res.status == "execution_only" and not SAMPLE_VIDEO.exists():
        print(f"\nFor FULL REAL VERIFIED, place a real walking video at:\n  {SAMPLE_VIDEO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
