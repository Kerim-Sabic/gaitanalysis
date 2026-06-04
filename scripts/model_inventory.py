"""Print an unambiguous local model/runtime/inference inventory."""
from __future__ import annotations

from _vision import REPO_ROOT, fix_hint
from verify_all_vision_models import verify_all


def _size_mb(pattern: str) -> float:
    return sum(path.stat().st_size for path in REPO_ROOT.glob(pattern)) / 1_000_000


SIZES = {
    "MediaPipe Full": "models/pose/mediapipe/pose_landmarker_full.task",
    "MediaPipe Heavy": "models/pose/mediapipe/pose_landmarker_heavy.task",
    "Ultralytics Pose": "models/pose/ultralytics/yolov8n-pose.pt",
    "MMPose RTMW": "models/pose/rtmw/*.pth",
    "MMPose RTMW3D": "models/pose/rtmw3d/*.pth",
    "SAM2.1 Tiny": "models/segmentation/sam2.1_hiera_tiny.pt",
    "Depth Anything V2": "models/depth/Depth-Anything-V2-*/*.pth",
    "WHAM": "models/pose/wham/checkpoints/*.pth.tar",
}


def main() -> int:
    results = verify_all()
    print("MODEL                 DEP WEIGHT CONFIG LOAD INFER OUTPUT PIPELINE SIZE_MB STATUS")
    for item in results:
        size = _size_mb(SIZES[item["model"]])
        print(
            f"{item['model'][:21]:21s} "
            f"{str(item.get('dependencies_installed', False))[0]:>3s} "
            f"{str(item.get('weights_present', False))[0]:>6s} "
            f"{str(item.get('config_present', False))[0]:>6s} "
            f"{str(item.get('model_loads', False))[0]:>4s} "
            f"{str(item.get('inference_runs', False))[0]:>5s} "
            f"{str(item.get('output_detected', False))[0]:>6s} "
            f"{str(item.get('integrated_into_pipeline', False))[0]:>8s} "
            f"{size:7.1f} {item['status']}"
        )
        if item.get("error"):
            print(f"  Blocker: {item['error']}")
            print(f"  Exact fix: {fix_hint(item)}")
        for key in ("isolated_runtime", "config_path", "checkpoint_path", "detector_path", "device"):
            if item.get(key):
                print(f"  {key}: {item[key]}")
    baseline_ok = all(item["status"] == "WORKING" for item in results[:3])
    advanced_ok = any(item["status"] == "WORKING" for item in results[3:7])
    return 0 if baseline_ok and advanced_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
