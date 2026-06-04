"""Single source of truth for real pose backend availability and selection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Type

from app.pipeline.pose.auto_best_adapter import AutoBestPoseEstimator
from app.pipeline.pose.base import BasePoseEstimator
from app.pipeline.pose.mediapipe_adapter import (
    MediaPipeFullPoseEstimator,
    MediaPipeHeavyPoseEstimator,
)
from app.pipeline.pose.mmpose_adapter import MMPoseRTMW3DPoseEstimator, MMPoseRTMWPoseEstimator
from app.pipeline.pose.simulated import SimulatedPoseEstimator
from app.pipeline.pose.ultralytics_adapter import UltralyticsPoseEstimator
from app.schemas import AnalysisMode


@dataclass
class BackendSpec:
    name: str
    kind: str
    adapter: Type[BasePoseEstimator]
    analysis_mode: AnalysisMode
    availability_error: Callable[[], Optional[str]]
    feet_keypoints: bool = False


def _none() -> Optional[str]:
    return None


REGISTRY: dict[str, BackendSpec] = {
    "auto_best": BackendSpec(
        "auto_best", "real", AutoBestPoseEstimator,
        AnalysisMode.real_mediapipe_tasks, AutoBestPoseEstimator.availability_error,
        feet_keypoints=True,
    ),
    "mmpose_rtmw": BackendSpec(
        "mmpose_rtmw", "real", MMPoseRTMWPoseEstimator,
        AnalysisMode.real_mmpose, MMPoseRTMWPoseEstimator.availability_error,
        feet_keypoints=True,
    ),
    "mmpose_rtmw3d": BackendSpec(
        "mmpose_rtmw3d", "real", MMPoseRTMW3DPoseEstimator,
        AnalysisMode.real_mmpose, MMPoseRTMW3DPoseEstimator.availability_error,
        feet_keypoints=True,
    ),
    "mediapipe_tasks_heavy": BackendSpec(
        "mediapipe_tasks_heavy", "real", MediaPipeHeavyPoseEstimator,
        AnalysisMode.real_mediapipe_tasks, MediaPipeHeavyPoseEstimator.availability_error,
        feet_keypoints=True,
    ),
    "mediapipe_tasks_full": BackendSpec(
        "mediapipe_tasks_full", "real", MediaPipeFullPoseEstimator,
        AnalysisMode.real_mediapipe_tasks, MediaPipeFullPoseEstimator.availability_error,
        feet_keypoints=True,
    ),
    "ultralytics_pose": BackendSpec(
        "ultralytics_pose", "real", UltralyticsPoseEstimator,
        AnalysisMode.real_ultralytics_pose, UltralyticsPoseEstimator.availability_error,
        feet_keypoints=False,
    ),
    "demo": BackendSpec(
        "demo", "demo", SimulatedPoseEstimator, AnalysisMode.demo_simulated, _none,
    ),
}

ALIASES = {
    "auto": "auto_best",
    "mediapipe": "mediapipe_tasks_full",
    "mediapipe_tasks": "mediapipe_tasks_full",
    "mmpose": "mmpose_rtmw",
    "ultralytics": "ultralytics_pose",
}

AUTO_ORDER = [
    "mmpose_rtmw",
    "mediapipe_tasks_heavy",
    "mediapipe_tasks_full",
    "ultralytics_pose",
]


def canonical(name: str) -> str:
    name = (name or "").lower()
    return ALIASES.get(name, name)


def is_real_backend_available(name: str) -> bool:
    spec = REGISTRY.get(canonical(name))
    return bool(spec and spec.kind == "real" and spec.adapter.is_available())


def available_real_backends() -> list[str]:
    return [name for name in AUTO_ORDER if is_real_backend_available(name)]


def all_backend_names() -> list[str]:
    return list(REGISTRY)


def resolve_real_backend(preference: str) -> Optional[str]:
    pref = canonical(preference or "auto_best")
    if pref == "demo":
        return None
    if pref == "auto_best":
        return "auto_best" if available_real_backends() else None
    spec = REGISTRY.get(pref)
    if spec is None or spec.kind != "real":
        return None
    return pref if spec.adapter.is_available() else None


def analysis_mode_for_backend(name: str) -> AnalysisMode:
    spec = REGISTRY.get(canonical(name))
    return spec.analysis_mode if spec else AnalysisMode.failed
