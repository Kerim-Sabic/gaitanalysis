"""Shared helpers for executable vision-model verification scripts."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"

POSE_BACKENDS = {
    "MediaPipe Full": ("app.pipeline.pose.mediapipe_adapter", "MediaPipeFullPoseEstimator"),
    "MediaPipe Heavy": ("app.pipeline.pose.mediapipe_adapter", "MediaPipeHeavyPoseEstimator"),
    "Ultralytics Pose": ("app.pipeline.pose.ultralytics_adapter", "UltralyticsPoseEstimator"),
    "MMPose RTMW": ("app.pipeline.pose.mmpose_adapter", "MMPoseRTMWPoseEstimator"),
    "MMPose RTMW3D": ("app.pipeline.pose.mmpose_adapter", "MMPoseRTMW3DPoseEstimator"),
}


def have_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def classify_error(error: str) -> str:
    lowered = error.lower()
    if "mmcv._ext" in lowered or "compiled mmcv" in lowered:
        return "DOCKER_REQUIRED"
    if "licensed" in lowered or "smpl_neutral.pkl" in lowered:
        return "BLOCKED_LICENSED_ASSETS"
    if "config" in lowered:
        return "BLOCKED_CONFIG"
    if "checkpoint" in lowered or "weight" in lowered or "model file" in lowered:
        return "BLOCKED_WEIGHT"
    if "import" in lowered or any(name in lowered for name in ("mmpose", "mmcv", "mmengine", "torch")):
        return "BLOCKED_DEPENDENCY"
    return "BLOCKED_RUNTIME"


def run_isolated_verifier(script_name: str, venv_name: str) -> dict[str, Any] | None:
    """Delegate an advanced check to its isolated venv and parse its JSON result."""
    python = REPO_ROOT / "apps" / "api" / venv_name / "Scripts" / "python.exe"
    if not python.exists() or Path(sys.executable).resolve() == python.resolve():
        return None
    process = subprocess.run(
        [str(python), str(REPO_ROOT / "scripts" / script_name), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    for line in reversed(process.stdout.splitlines()):
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        result["isolated_runtime"] = str(python.relative_to(REPO_ROOT))
        return result
    return {
        "model": script_name,
        "weights_present": False,
        "dependencies_installed": False,
        "config_present": False,
        "model_loads": False,
        "inference_runs": False,
        "output_detected": False,
        "integrated_into_pipeline": False,
        "status": "BLOCKED_RUNTIME",
        "error": process.stderr.strip() or process.stdout.strip() or "Isolated verifier returned no JSON.",
        "isolated_runtime": str(python.relative_to(REPO_ROOT)),
    }


def load_sample_frames(limit: int = 3) -> tuple[np.ndarray, float]:
    """Decode evenly spaced real sample frames without importing the API video stack."""
    import cv2

    if not SAMPLE.exists():
        raise FileNotFoundError(f"Sample video missing: {SAMPLE}")
    capture = cv2.VideoCapture(str(SAMPLE))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open sample video: {SAMPLE}")
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    frames = []
    for index in np.unique(np.linspace(0, frame_count - 1, max(1, limit)).astype(int)):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError(f"No frames decoded from sample video: {SAMPLE}")
    return np.stack(frames), fps


def verify_pose_backend(label: str, max_frames: int = 60) -> dict[str, Any]:
    module_name, class_name = POSE_BACKENDS[label]
    adapter = getattr(__import__(module_name, fromlist=[class_name]), class_name)
    result: dict[str, Any] = {
        "model": label,
        "weights_present": False,
        "dependencies_installed": False,
        "config_present": True,
        "model_loads": False,
        "inference_runs": False,
        "output_detected": False,
        "integrated_into_pipeline": label != "MMPose RTMW3D",
        "status": "BLOCKED",
        "error": "",
    }
    error = getattr(adapter, "availability_error", lambda: None)()
    if label.startswith("MMPose"):
        result["dependencies_installed"] = all(
            have_module(name) for name in ("torch", "mmengine", "mmcv", "mmpose")
        )
        versions = {}
        for name in ("torch", "torchvision", "mmengine", "mmcv", "mmdet", "mmpose", "ultralytics"):
            try:
                versions[name] = str(getattr(__import__(name), "__version__", "unknown"))
            except Exception:
                versions[name] = "unavailable"
        result["dependency_versions"] = versions
        result["config_present"] = False
    try:
        estimator = adapter()
        result["weights_present"] = bool(getattr(estimator, "model_file", ""))
        result["config_present"] = bool(getattr(estimator, "config", True))
        result.update({
            "checkpoint_path": str(getattr(estimator, "checkpoint", "") or getattr(estimator, "model_file", "")),
            "config_path": str(getattr(estimator, "config", "") or ""),
            "detector_path": str(getattr(estimator, "detector_path", "") or ""),
            "device": str(getattr(estimator, "device", "cpu")),
        })
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    if not label.startswith("MMPose"):
        result["dependencies_installed"] = not bool(
            error and classify_error(error) == "BLOCKED_DEPENDENCY"
        )
    if error and classify_error(error) == "BLOCKED_CONFIG":
        result["config_present"] = False
    if error:
        result["status"] = classify_error(error)
        result["error"] = error
        return result
    if not SAMPLE.exists():
        result["status"] = "BLOCKED"
        result["error"] = f"Sample video missing: {SAMPLE}"
        return result
    try:
        from app.pipeline.pose.quality_comparator import score_pose_sequence
        from app.pipeline.video_processor import VideoProcessor

        decoded = VideoProcessor(max_frames=max_frames).load(SAMPLE, min_seconds=0.2)
        estimator = adapter()
        started = time.perf_counter()
        seq = estimator.estimate_2d_pose(decoded.frames, decoded.fps)
        elapsed = time.perf_counter() - started
        score = score_pose_sequence(seq, backend=getattr(estimator, "backend_id", label), inference_time_sec=elapsed)
        result.update({
            "weights_present": bool(getattr(estimator, "model_file", "")),
            "model_loads": True,
            "inference_runs": True,
            "output_detected": score["valid_pose_percentage"] > 0,
            "score": score,
            "status": "WORKING" if score["valid_pose_percentage"] > 0 else "PARTIAL",
            "error": "" if score["valid_pose_percentage"] > 0 else "Inference ran but no valid pose frames were detected.",
        })
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["status"] = "BLOCKED"
    return result


FIX_HINTS: dict[str, str] = {
    "SAM2.1 Tiny": "pip install git+https://github.com/facebookresearch/sam2.git "
                   "(needs torch); or: docker compose --profile sam2 up --build api-sam2",
    "MMPose RTMW": "Start Docker Desktop, then run: "
                   "docker compose --profile mmpose up --build api-mmpose",
    "MMPose RTMW3D": "Add the matching RTMW3D config and verified 3D PoseSequence mapping, "
                     "then run: docker compose --profile mmpose up --build api-mmpose",
    "Depth Anything V2": "pip install torch transformers and the Depth-Anything-V2 source; "
                         "weights already under models/depth/ (optional helper, not required).",
    "WHAM": "Obtain licensed SMPL body models from https://smpl.is.tue.mpg.de and place "
            "SMPL_NEUTRAL.pkl (and male/female) under models/body_models/smpl/, install "
            "torch + smplx + wham; checkpoints already under models/pose/wham/.",
}


def fix_hint(result: dict[str, Any]) -> str:
    if result.get("status") == "WORKING":
        return ""
    return result.get("fix") or FIX_HINTS.get(result.get("model", ""), "See docs/deployment.md.")


def print_result(result: dict[str, Any]) -> None:
    print(f"=== {result['model']} verification ===")
    for key in (
        "weights_present", "dependencies_installed", "config_present", "model_loads",
        "inference_runs", "output_detected", "integrated_into_pipeline", "status",
    ):
        print(f"{key:25s}: {result.get(key)}")
    score = result.get("score") or {}
    if score:
        print(f"valid_pose_percentage    : {score.get('valid_pose_percentage', 0):.1f}")
        print(f"average_confidence       : {score.get('average_confidence', 0):.3f}")
        print(f"final_score              : {score.get('final_score', 0):.1f}")
    if result.get("error"):
        print(f"blocker                  : {result['error']}")
    for key in (
        "isolated_runtime", "dependency_versions", "checkpoint_path", "config_path",
        "detector_path", "device",
        "frames_segmented", "person_area_ratio", "bbox_stability",
        "feet_region_visibility_estimate", "full_body_visibility_estimate",
        "frames_processed", "output_shape", "relative_depth_min", "relative_depth_median",
        "relative_depth_max", "relative_depth_std", "processing_time_sec",
    ):
        if key in result and result[key] not in ("", None):
            print(f"{key:25s}: {result[key]}")
    fx = fix_hint(result)
    if fx:
        print(f"fix                      : {fx}")
    # Exact final status line per model.
    label = {
        "Depth Anything V2": "DEPTH ANYTHING",
        "SAM2.1 Tiny": "SAM2",
        "MMPose RTMW": "MMPOSE",
        "MMPose RTMW3D": "MMPOSE RTMW3D",
    }.get(result["model"], result["model"].split()[0].upper())
    if result.get("status") == "WORKING":
        print(f"{label} VERIFIED")
    else:
        print(f"BLOCKED: {result['status']} — {result.get('error') or 'unavailable'}")


def working_exit(result: dict[str, Any]) -> int:
    return 0 if result["status"] == "WORKING" else 1
