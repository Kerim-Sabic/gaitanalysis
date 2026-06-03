"""Model setup helper: checks environment and prepares directories.

    python scripts/download_models.py

Does NOT fake installs. If MediaPipe is missing or non-functional it prints the
exact command to run. MediaPipe ships as a pip wheel (no separate weight
download is required for the default pose graph).
"""
from __future__ import annotations

import platform
import sys

import _bootstrap  # noqa: F401  (sys.path setup)

REPO_ROOT = _bootstrap.REPO_ROOT


def main() -> int:
    print("=== Horalix model setup ===")
    print(f"Python : {sys.version.split()[0]} ({platform.system()} {platform.machine()})")

    ok_py = sys.version_info >= (3, 10)
    print(f"Python >= 3.10 : {'yes' if ok_py else 'NO (3.10+ required)'}")

    # Directories.
    for rel in ("models/pose", "models/segmentation", "models/tracking", "models/gait",
                "data/sample_videos", "data/uploads", "data/processed", "data/reports"):
        (REPO_ROOT / rel).mkdir(parents=True, exist_ok=True)
    print("Model/data directories : ready")

    # MediaPipe functional check (import + solutions.pose + native bindings).
    from app.pipeline.pose.mediapipe_adapter import (
        MediaPipePoseEstimator,
        mediapipe_version,
    )

    available = MediaPipePoseEstimator.is_available()
    print(f"MediaPipe import       : version {mediapipe_version()}")
    print(f"MediaPipe functional   : {'yes' if available else 'NO'}")
    if not available:
        print(f"  reason: {MediaPipePoseEstimator.availability_error()}")
        print("  fix:    pip install mediapipe   (Python 3.10–3.12, 64-bit)")
        print("  then re-run: python scripts/verify_models.py")
    else:
        print("  MediaPipe Pose backend is importable and ready.")

    print("\nSample video: place a real walking clip at "
          "data/sample_videos/walk_test.mp4 for full verification.")
    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
