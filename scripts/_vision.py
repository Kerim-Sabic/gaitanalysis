"""Shared helpers for executable vision-model verification scripts."""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from typing import Any

import numpy as np

import _bootstrap  # noqa: F401

from app.pipeline.pose.mediapipe_adapter import (
    MediaPipeFullPoseEstimator,
    MediaPipeHeavyPoseEstimator,
)
from app.pipeline.pose.mmpose_adapter import MMPoseRTMW3DPoseEstimator, MMPoseRTMWPoseEstimator
from app.pipeline.pose.quality_comparator import score_pose_sequence
from app.pipeline.pose.ultralytics_adapter import UltralyticsPoseEstimator
from app.pipeline.video_processor import VideoProcessor

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"

POSE_BACKENDS = {
    "MediaPipe Full": MediaPipeFullPoseEstimator,
    "MediaPipe Heavy": MediaPipeHeavyPoseEstimator,
    "Ultralytics Pose": UltralyticsPoseEstimator,
    "MMPose RTMW": MMPoseRTMWPoseEstimator,
    "MMPose RTMW3D": MMPoseRTMW3DPoseEstimator,
}


def have_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def classify_error(error: str) -> str:
    lowered = error.lower()
    if "config" in lowered:
        return "MISSING_CONFIG"
    if "checkpoint" in lowered or "weight" in lowered or "model file" in lowered:
        return "MISSING_WEIGHT"
    if "import" in lowered or any(name in lowered for name in ("mmpose", "mmcv", "mmengine", "torch")):
        return "MISSING_DEPENDENCY"
    return "BLOCKED"


def verify_pose_backend(label: str, max_frames: int = 60) -> dict[str, Any]:
    adapter = POSE_BACKENDS[label]
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
        result["config_present"] = False
    try:
        estimator = adapter()
        result["weights_present"] = bool(getattr(estimator, "model_file", ""))
        result["config_present"] = bool(getattr(estimator, "config", True))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    if not label.startswith("MMPose"):
        result["dependencies_installed"] = not bool(
            error and classify_error(error) == "MISSING_DEPENDENCY"
        )
    if error and classify_error(error) == "MISSING_CONFIG":
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


def working_exit(result: dict[str, Any]) -> int:
    return 0 if result["status"] in ("WORKING", "PARTIAL", "NOT_REQUIRED") else 1
