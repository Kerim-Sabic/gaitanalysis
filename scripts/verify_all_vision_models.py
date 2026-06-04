"""Execute and summarize all required/optional real vision model checks."""
from __future__ import annotations

from _vision import REPO_ROOT, print_result, verify_pose_backend
from verify_depth_anything import verify as verify_depth
from verify_sam2 import verify as verify_sam2


def verify_wham():
    checkpoint = REPO_ROOT / "models/pose/wham/checkpoints/wham_vit_w_3dpw.pth.tar"
    body_models = REPO_ROOT / "models/pose/wham/dataset/body_models"
    smpl = [
        body_models / "SMPL_NEUTRAL.pkl",
        body_models / "SMPL_MALE.pkl",
        body_models / "SMPL_FEMALE.pkl",
    ]
    smpl_present = any(path.exists() for path in smpl)
    return {
        "model": "WHAM",
        "weights_present": checkpoint.exists(),
        "dependencies_installed": False,
        "config_present": smpl_present,
        "model_loads": False,
        "inference_runs": False,
        "output_detected": False,
        "integrated_into_pipeline": False,
        "status": "BLOCKED",
        "error": "blocked_missing_smpl_assets" if not smpl_present else "WHAM runtime not installed.",
    }


def verify_all():
    return [
        verify_pose_backend("MediaPipe Full"),
        verify_pose_backend("MediaPipe Heavy"),
        verify_pose_backend("Ultralytics Pose"),
        verify_pose_backend("MMPose RTMW"),
        verify_pose_backend("MMPose RTMW3D"),
        verify_sam2(),
        verify_depth(),
        verify_wham(),
    ]


if __name__ == "__main__":
    results = verify_all()
    print("MODEL                 WEIGHT DEP CONFIG LOAD INFER OUTPUT INTEGRATED STATUS")
    for item in results:
        print(
            f"{item['model'][:21]:21s} "
            f"{str(item['weights_present'])[0]:>6s} {str(item['dependencies_installed'])[0]:>3s} "
            f"{str(item['config_present'])[0]:>6s} {str(item['model_loads'])[0]:>4s} "
            f"{str(item['inference_runs'])[0]:>5s} {str(item['output_detected'])[0]:>6s} "
            f"{str(item['integrated_into_pipeline'])[0]:>10s} {item['status']}"
        )
    print()
    for item in results:
        if item.get("error"):
            print_result(item)
            print()
    required = results[:3]
    raise SystemExit(0 if all(item["status"] == "WORKING" for item in required) else 1)
