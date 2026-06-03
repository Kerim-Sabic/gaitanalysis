"""Pose backend registry.

Maps backend identifiers to adapter classes and reports which *real* backends
can actually run. Single source of truth for "what can run real analysis now".

Backends:
  * mediapipe_tasks  — MediaPipe Tasks PoseLandmarker (preferred; heel/foot_index)
  * ultralytics_pose — Ultralytics YOLO-Pose (real fallback; COCO-17, no feet)
  * demo             — simulated (explicit only; never auto-selected for real)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Type

from app.pipeline.pose.base import BasePoseEstimator
from app.pipeline.pose.mediapipe_adapter import MediaPipePoseEstimator
from app.pipeline.pose.simulated import SimulatedPoseEstimator
from app.pipeline.pose.ultralytics_adapter import UltralyticsPoseEstimator
from app.schemas import AnalysisMode


@dataclass
class BackendSpec:
    name: str
    kind: str  # "real" | "demo"
    adapter: Type[BasePoseEstimator]
    analysis_mode: AnalysisMode
    availability_error: Callable[[], Optional[str]]
    feet_keypoints: bool = False


def _none() -> Optional[str]:
    return None


REGISTRY: dict[str, BackendSpec] = {
    "mediapipe_tasks": BackendSpec(
        "mediapipe_tasks", "real", MediaPipePoseEstimator,
        AnalysisMode.real_mediapipe_tasks, MediaPipePoseEstimator.availability_error,
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

# Aliases accepted from HORALIX_POSE_BACKEND for convenience/back-compat.
ALIASES = {"mediapipe": "mediapipe_tasks", "ultralytics": "ultralytics_pose"}

# Real backends in auto-resolution preference order (MediaPipe first: feet).
AUTO_ORDER = ["mediapipe_tasks", "ultralytics_pose"]


def canonical(name: str) -> str:
    name = (name or "").lower()
    return ALIASES.get(name, name)


def is_real_backend_available(name: str) -> bool:
    spec = REGISTRY.get(canonical(name))
    if not spec or spec.kind != "real":
        return False
    return spec.adapter.is_available()


def available_real_backends() -> list[str]:
    return [n for n in AUTO_ORDER if is_real_backend_available(n)]


def all_backend_names() -> list[str]:
    return ["mediapipe_tasks", "ultralytics_pose", "demo"]


def resolve_real_backend(preference: str) -> Optional[str]:
    """Resolve the configured preference to an available *real* backend name, or
    None if none available / the preference is demo-only."""
    pref = canonical(preference or "mediapipe_tasks")
    if pref == "demo":
        return None
    if pref == "auto":
        return next((n for n in AUTO_ORDER if is_real_backend_available(n)), None)
    spec = REGISTRY.get(pref)
    if spec is None or spec.kind != "real":
        return None
    return pref if spec.adapter.is_available() else None
