"""Inventory local model files, runtimes, configs, and integration state."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT


def have(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def files(pattern: str) -> list[Path]:
    return sorted(REPO_ROOT.glob(pattern))


def main() -> int:
    families = [
        ("MediaPipe Full", files("models/pose/mediapipe/pose_landmarker_full.task"), "mediapipe", True),
        ("MediaPipe Heavy", files("models/pose/mediapipe/pose_landmarker_heavy.task"), "mediapipe", True),
        ("Ultralytics Pose", files("models/pose/ultralytics/yolov8n-pose.pt"), "ultralytics", True),
        ("MMPose RTMW", files("models/pose/rtmw/*.pth"), "mmpose", True),
        ("MMPose RTMW3D", files("models/pose/rtmw3d/*.pth"), "mmpose", False),
        ("SAM2.1 Tiny", files("models/segmentation/sam2.1_hiera_tiny.pt"), "sam2", False),
        ("Depth Anything V2", files("models/depth/Depth-Anything-V2-*/*.pth"), "depth_anything_v2", False),
        ("WHAM", files("models/pose/wham/checkpoints/*.pth.tar"), "wham", False),
    ]
    print("MODEL                 FILES   SIZE(MB) RUNTIME CONFIG INTEGRATED")
    for name, found, runtime, integrated in families:
        size = sum(path.stat().st_size for path in found) / 1_000_000
        config = bool(files("models/pose/rtmw/configs/*.py")) if "MMPose" in name else True
        print(
            f"{name:21s} {len(found):5d} {size:10.1f} "
            f"{str(have(runtime)):7s} {str(config):6s} {str(integrated):10s}"
        )
        for path in found:
            print(f"  - {path.relative_to(REPO_ROOT)} ({path.stat().st_size / 1_000_000:.2f} MB)")
    print("\nWHAM status: blocked_missing_smpl_assets unless licensed SMPL*.pkl files are supplied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
