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
        # Per-request override of fast/full (set by the model loader from the
        # analysis setup); falls back to the server-configured mode when None.
        self.mode_override: str | None = None

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

    def _mode(self) -> str:
        from app.config import get_settings

        return (self.mode_override or get_settings().auto_best_mode or "fast").lower()

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        results: dict[str, tuple[PoseSequence, float]] = {}
        estimators: dict[str, BasePoseEstimator] = {}
        failures: dict[str, str] = {}

        # "fast" mode: run ONLY the single preferred available backend (no
        # redundant multi-backend inference). "full" mode: run all and compare.
        fast = self._mode() == "fast"
        candidates = list(self.CANDIDATES)
        ran_any = False
        for name, adapter in candidates:
            if not adapter.is_available():
                failures[name] = getattr(adapter, "availability_error", lambda: None)() or "unavailable"
                continue
            if fast and ran_any:
                # Preferred backend already ran; record others as skipped.
                failures[name] = "skipped (auto_best_mode=fast)"
                continue
            try:
                estimator = adapter()
                started = time.perf_counter()
                sequence = estimator.estimate_2d_pose(frames, fps)
                results[name] = (sequence, time.perf_counter() - started)
                estimators[name] = estimator
                ran_any = True
            except Exception as exc:
                failures[name] = f"{type(exc).__name__}: {exc}"
        comparison = compare_backend_results(results, failures)
        self.selected_backend = comparison["selected_backend"]
        self.selection_reason = comparison["selection_reason"]
        if fast and self.selected_backend:
            self.selection_reason = (
                f"fast mode: ran the preferred available backend "
                f"({self.selected_backend}) without full multi-backend comparison "
                f"(set HORALIX_AUTO_BEST_MODE=full to compare all)."
            )
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
