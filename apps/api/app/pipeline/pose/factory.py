"""Pose backend selection.

``select_pose_estimator`` resolves the configured preference to a concrete
adapter, transparently falling back to the simulated estimator when no real
model is installed. The returned ``analysis_mode`` tells the rest of the system
whether output is clinical-candidate or demo.
"""
from __future__ import annotations

from app.schemas import AnalysisMode

from .base import BasePoseEstimator
from .mediapipe_adapter import MediaPipePoseEstimator
from .mmpose_adapter import MMPosePoseEstimator
from .simulated import SimulatedPoseEstimator


def select_pose_estimator(
    backend: str = "auto",
    demo_preset: str | None = None,
) -> tuple[BasePoseEstimator, AnalysisMode]:
    """Return ``(estimator, analysis_mode)``.

    A demo preset always forces the simulated estimator (demo mode). Otherwise we
    honour the preference, falling back through MMPose -> MediaPipe -> simulated.
    """
    if demo_preset:
        return SimulatedPoseEstimator.from_preset(demo_preset), AnalysisMode.demo

    if backend == "simulated":
        return SimulatedPoseEstimator(), AnalysisMode.demo

    if backend == "mmpose":
        if MMPosePoseEstimator.is_available():
            return MMPosePoseEstimator(), AnalysisMode.clinical
        return SimulatedPoseEstimator(), AnalysisMode.demo

    if backend == "mediapipe":
        if MediaPipePoseEstimator.is_available():
            return MediaPipePoseEstimator(), AnalysisMode.clinical
        return SimulatedPoseEstimator(), AnalysisMode.demo

    # auto: best installed real model, else simulated fallback.
    if MMPosePoseEstimator.is_available():
        return MMPosePoseEstimator(), AnalysisMode.clinical
    if MediaPipePoseEstimator.is_available():
        return MediaPipePoseEstimator(), AnalysisMode.clinical
    return SimulatedPoseEstimator(), AnalysisMode.demo
