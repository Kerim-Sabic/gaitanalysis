"""Pose backend selection (safe wrapper).

This delegates to the model loader so there is a SINGLE real-selection path. It
never returns a simulated estimator for a real-backend request — demo is only
returned when a demo preset is explicitly provided. Real selection raises
``ModelUnavailableError`` when no real backend is available (no silent fallback).
"""
from __future__ import annotations

from app.schemas import AnalysisMode

from .base import BasePoseEstimator


def select_pose_estimator(
    backend: str = "auto",
    demo_preset: str | None = None,
) -> tuple[BasePoseEstimator, AnalysisMode]:
    """Return ``(estimator, analysis_mode)``.

    Demo preset -> simulated estimator (demo_simulated). Otherwise delegate to the
    model loader's real selection, which raises ModelUnavailableError if no real
    backend is available. There is NO silent fallback to simulated for real runs.
    """
    if demo_preset:
        from .simulated import SimulatedPoseEstimator

        return SimulatedPoseEstimator.from_preset(demo_preset), AnalysisMode.demo_simulated

    from app.models.model_loader import get_model_loader

    return get_model_loader().get_real_estimator()
