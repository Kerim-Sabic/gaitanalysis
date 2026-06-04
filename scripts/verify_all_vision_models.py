"""Execute and summarize required and optional real vision model checks."""
from __future__ import annotations

from _vision import fix_hint, print_result, verify_pose_backend
from verify_depth_anything import verify as verify_depth
from verify_mmpose import verify as verify_mmpose
from verify_sam2 import verify as verify_sam2
from verify_wham import verify as verify_wham


def verify_all():
    mmpose = verify_mmpose()
    return [
        verify_pose_backend("MediaPipe Full"),
        verify_pose_backend("MediaPipe Heavy"),
        verify_pose_backend("Ultralytics Pose"),
        mmpose["rtmw"],
        mmpose["rtmw3d"],
        verify_sam2(),
        verify_depth(),
        verify_wham(),
    ]


if __name__ == "__main__":
    results = verify_all()
    print("MODEL                 DEP WEIGHT CONFIG LOAD INFER OUTPUT PIPELINE STATUS")
    for item in results:
        print(
            f"{item['model'][:21]:21s} "
            f"{str(item.get('dependencies_installed', False))[0]:>3s} "
            f"{str(item.get('weights_present', False))[0]:>6s} "
            f"{str(item.get('config_present', False))[0]:>6s} "
            f"{str(item.get('model_loads', False))[0]:>4s} "
            f"{str(item.get('inference_runs', False))[0]:>5s} "
            f"{str(item.get('output_detected', False))[0]:>6s} "
            f"{str(item.get('integrated_into_pipeline', False))[0]:>8s} "
            f"{item['status']}"
        )
    print()
    for item in results:
        if item.get("error"):
            print(f"{item['model']}: {item['error']}")
            print(f"Exact fix: {fix_hint(item)}")
    print()
    for item in results:
        print_result(item)
        print()
    baseline_ok = all(item["status"] == "WORKING" for item in results[:3])
    advanced_ok = any(item["status"] == "WORKING" for item in results[3:7])
    raise SystemExit(0 if baseline_ok and advanced_ok else 1)
