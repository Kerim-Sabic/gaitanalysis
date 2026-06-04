"""Run available real pose backends and select the best measured output."""
from __future__ import annotations

import time

import numpy as np

from .base import BasePoseEstimator, PoseModelInfo, PoseSequence
from .mediapipe_adapter import MediaPipeFullPoseEstimator, MediaPipeHeavyPoseEstimator
from .mmpose_adapter import MMPoseRTMWPoseEstimator
from .quality_comparator import compare_backend_results
from .ultralytics_adapter import LIMITATION as ULTRALYTICS_LIMITATION
from .ultralytics_adapter import UltralyticsPoseEstimator


class AutoBestPoseEstimator(BasePoseEstimator):
    backend_id = "auto_best"
    CANDIDATES = [
        ("mmpose_rtmw", MMPoseRTMWPoseEstimator),
        ("mediapipe_tasks_heavy", MediaPipeHeavyPoseEstimator),
        ("mediapipe_tasks_full", MediaPipeFullPoseEstimator),
        ("ultralytics_pose", UltralyticsPoseEstimator),
    ]

    def __init__(self):
        self.selected_backend = ""
        self.selected_estimator: BasePoseEstimator | None = None
        self.selection_reason = ""
        self.backend_scores: dict[str, dict] = {}
        self.backend_failures: dict[str, str] = {}
        self.model_limitations: list[str] = []
        self.device = "cpu"
        self.model_file = ""

    @classmethod
    def is_available(cls) -> bool:
        return any(adapter.is_available() for _, adapter in cls.CANDIDATES)

    @classmethod
    def availability_error(cls) -> str | None:
        if cls.is_available():
            return None
        failures = []
        for name, adapter in cls.CANDIDATES:
            detail = getattr(adapter, "availability_error", lambda: None)()
            failures.append(f"{name}: {detail or 'unavailable'}")
        return "; ".join(failures)

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        results: dict[str, tuple[PoseSequence, float]] = {}
        estimators: dict[str, BasePoseEstimator] = {}
        failures: dict[str, str] = {}
        for name, adapter in self.CANDIDATES:
            if not adapter.is_available():
                failures[name] = getattr(adapter, "availability_error", lambda: None)() or "unavailable"
                continue
            try:
                estimator = adapter()
                started = time.perf_counter()
                sequence = estimator.estimate_2d_pose(frames, fps)
                results[name] = (sequence, time.perf_counter() - started)
                estimators[name] = estimator
            except Exception as exc:
                failures[name] = f"{type(exc).__name__}: {exc}"
        comparison = compare_backend_results(results, failures)
        self.selected_backend = comparison["selected_backend"]
        self.selection_reason = comparison["selection_reason"]
        self.backend_scores = comparison["backend_scores"]
        self.backend_failures = comparison["backend_failures"]
        self.selected_estimator = estimators[self.selected_backend]
        self.device = str(getattr(self.selected_estimator, "device", "cpu"))
        self.model_file = str(getattr(self.selected_estimator, "model_file", ""))
        self.model_limitations = list(self.selected_estimator.get_model_info().notes)
        if self.selected_backend == "ultralytics_pose":
            self.model_limitations.append(ULTRALYTICS_LIMITATION)
        return results[self.selected_backend][0]

    def get_model_info(self) -> PoseModelInfo:
        if self.selected_estimator is not None:
            return self.selected_estimator.get_model_info()
        return PoseModelInfo(
            name="Automatic best available real pose backend",
            version="selection pending",
            keypoint_format="backend dependent",
            notes=["Auto mode evaluates real backends only; demo is never selected."],
        )
