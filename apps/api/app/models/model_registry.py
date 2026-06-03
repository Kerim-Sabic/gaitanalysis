"""Pose backend registry.

Maps backend identifiers to adapter classes and reports which *real* backends
are actually available (their inference engine imports and initialises). This is
the single source of truth for "what can run real analysis right now".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Type

from app.pipeline.pose.base import BasePoseEstimator
from app.pipeline.pose.mediapipe_adapter import MediaPipePoseEstimator
from app.pipeline.pose.mmpose_adapter import MMPosePoseEstimator
from app.pipeline.pose.simulated import SimulatedPoseEstimator
from app.schemas import AnalysisMode


@dataclass
class BackendSpec:
    name: str
    kind: str  # "real" | "demo"
    adapter: Type[BasePoseEstimator]
    analysis_mode: AnalysisMode
    availability_error: Callable[[], Optional[str]]


def _mediapipe_error() -> Optional[str]:
    return MediaPipePoseEstimator.availability_error()


def _mmpose_error() -> Optional[str]:
    return None if MMPosePoseEstimator.is_available() else "MMPose is not installed."


def _none() -> Optional[str]:
    return None


# Canonical backends. "mmpose_future" is an alias used by the env var contract.
REGISTRY: dict[str, BackendSpec] = {
    "mediapipe": BackendSpec(
        "mediapipe", "real", MediaPipePoseEstimator,
        AnalysisMode.real_mediapipe, _mediapipe_error,
    ),
    "mmpose": BackendSpec(
        "mmpose", "real", MMPosePoseEstimator, AnalysisMode.real_mmpose, _mmpose_error,
    ),
    "mmpose_future": BackendSpec(
        "mmpose_future", "real", MMPosePoseEstimator, AnalysisMode.real_mmpose, _mmpose_error,
    ),
    "demo": BackendSpec(
        "demo", "demo", SimulatedPoseEstimator, AnalysisMode.demo_simulated, _none,
    ),
}

# Real backends in auto-resolution preference order.
AUTO_ORDER = ["mmpose", "mediapipe"]


def is_real_backend_available(name: str) -> bool:
    spec = REGISTRY.get(name)
    if not spec or spec.kind != "real":
        return False
    return spec.adapter.is_available()


def available_real_backends() -> list[str]:
    seen: list[str] = []
    for name in ("mediapipe", "mmpose"):
        if is_real_backend_available(name) and name not in seen:
            seen.append(name)
    return seen


def all_backend_names() -> list[str]:
    return ["mediapipe", "mmpose_future", "demo"]


def resolve_real_backend(preference: str) -> Optional[str]:
    """Resolve the configured preference to a *real* backend name, or None if no
    real backend is available / the preference is demo-only."""
    pref = (preference or "mediapipe").lower()
    if pref == "demo":
        return None
    if pref == "auto":
        for name in AUTO_ORDER:
            if is_real_backend_available(name):
                return name
        return None
    canonical = "mmpose" if pref == "mmpose_future" else pref
    if canonical in REGISTRY and REGISTRY[canonical].kind == "real":
        return canonical if is_real_backend_available(canonical) else None
    return None
