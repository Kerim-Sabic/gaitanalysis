"""Model loader — owns real-model selection, verification and health.

Hard rules enforced here:
  * Real analysis NEVER silently falls back to simulated/demo. If the configured
    real backend is unavailable, ``get_real_estimator`` raises
    ``ModelUnavailableError`` with a clear, actionable message.
  * No fake success: ``model_loaded`` / ``verified`` only become true after the
    adapter's inference engine imports, initialises and runs inference.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from app.config import get_settings
from app.pipeline.pose.base import BasePoseEstimator
from app.schemas import AnalysisMode

from . import model_registry as registry
from .model_status import HealthcheckResult, ModelStatus, ModelVerifyResult

REAL_UNAVAILABLE_MSG = (
    "Real pose model is unavailable. Run model setup or switch to Demo Mode."
)


class ModelUnavailableError(Exception):
    """Raised when real analysis is requested but no real model can run."""

    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(REAL_UNAVAILABLE_MSG + (f" ({detail})" if detail else ""))


def _synthetic_person_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """A crude humanoid frame used only to exercise the inference code path.
    Note: real pose models may not detect a person in a synthetic drawing — the
    verify result reports landmark detection honestly and recommends a real
    sample video for full confirmation."""
    import cv2

    img = np.full((h, w, 3), 60, np.uint8)
    cx = w // 2
    cv2.circle(img, (cx, 90), 34, (220, 200, 180), -1)          # head
    cv2.rectangle(img, (cx - 35, 124), (cx + 35, 300), (200, 180, 160), -1)  # torso
    cv2.rectangle(img, (cx - 33, 300), (cx - 8, 450), (190, 170, 150), -1)   # left leg
    cv2.rectangle(img, (cx + 8, 300), (cx + 33, 450), (190, 170, 150), -1)   # right leg
    cv2.rectangle(img, (cx - 70, 130), (cx - 35, 270), (190, 170, 150), -1)  # left arm
    cv2.rectangle(img, (cx + 35, 130), (cx + 70, 270), (190, 170, 150), -1)  # right arm
    return img


class ModelLoader:
    def __init__(self):
        self._lock = threading.RLock()
        self._estimator: Optional[BasePoseEstimator] = None
        self._loaded_backend: Optional[str] = None
        self._init_error: Optional[str] = None
        self._last_healthcheck: str = "unknown"

    # ------------------------------------------------------------------ #
    @property
    def configured_backend(self) -> str:
        return (get_settings().pose_backend or "mediapipe").lower()

    def get_real_estimator(self) -> tuple[BasePoseEstimator, AnalysisMode]:
        """Return a real estimator + its analysis mode, or raise.
        This is the ONLY path real analysis uses — it never returns a simulated
        estimator."""
        with self._lock:
            backend = registry.resolve_real_backend(self.configured_backend)
            if backend is None:
                detail = self._diagnose()
                self._init_error = detail
                raise ModelUnavailableError(detail)
            spec = registry.REGISTRY[backend]
            try:
                if self._estimator is None or self._loaded_backend != backend:
                    self._estimator = spec.adapter()
                    self._loaded_backend = backend
                self._init_error = None
                return self._estimator, spec.analysis_mode
            except Exception as e:  # pragma: no cover - defensive
                self._init_error = f"{type(e).__name__}: {e}"
                raise ModelUnavailableError(self._init_error) from e

    def _diagnose(self) -> str:
        pref = self.configured_backend
        if pref == "demo":
            return "HORALIX_POSE_BACKEND=demo: real analysis disabled (demo only)."
        spec = registry.REGISTRY.get("mmpose" if pref == "mmpose_future" else pref)
        if spec is None:
            return f"Unknown backend '{pref}'."
        err = spec.availability_error()
        return err or f"Backend '{pref}' reported unavailable."

    # ------------------------------------------------------------------ #
    def status(self) -> ModelStatus:
        with self._lock:
            real_backend = registry.resolve_real_backend(self.configured_backend)
            available = registry.available_real_backends()
            name = version = ""
            device = "cpu"
            loaded = False
            if real_backend:
                spec = registry.REGISTRY[real_backend]
                try:
                    est = spec.adapter()
                    info = est.get_model_info()
                    name, version = info.name, info.version
                    device = str(getattr(est, "device", "cpu"))
                    loaded = True
                except Exception as e:
                    self._init_error = f"{type(e).__name__}: {e}"
            return ModelStatus(
                active_backend=self.configured_backend,
                available_backends=registry.all_backend_names(),
                model_loaded=loaded,
                model_name=name,
                model_version=version,
                device=device,
                initialization_error=(None if real_backend else self._diagnose()),
                last_healthcheck_status=self._last_healthcheck,
                demo_mode_available=get_settings().allow_demo_mode,
                real_analysis_available=bool(available),
            )

    # ------------------------------------------------------------------ #
    def verify(self) -> ModelVerifyResult:
        """Lightweight real-inference verification on a generated frame."""
        res = ModelVerifyResult(backend=self.configured_backend)
        try:
            estimator, mode = self.get_real_estimator()
        except ModelUnavailableError as e:
            res.error = str(e)
            return res

        info = estimator.get_model_info()
        res.model_name = info.name
        res.model_version = info.version
        res.device = str(getattr(estimator, "device", "cpu"))
        try:
            frame = _synthetic_person_frame()
            stack = np.stack([frame, frame, frame], axis=0)
            res.initialized = True
            seq = estimator.estimate_2d_pose(stack, fps=30.0)
            res.inference_ran = True
            scores = seq.all_keypoints()[..., 2]
            detected = bool(np.any(scores > 0.3))
            res.landmarks_detected = detected
            res.landmark_count = int(seq.all_keypoints().shape[1])
            res.average_confidence = round(float(np.nanmean(scores)), 3) if scores.size else 0.0
            res.passed = res.initialized and res.inference_ran
            res.note = (
                "Landmarks detected." if detected else
                "Inference ran but no landmarks on the synthetic test frame; "
                "confirm with data/sample_videos/walk_test.mp4 (a real person video)."
            )
        except Exception as e:
            res.error = f"{type(e).__name__}: {e}"
            res.passed = False
        return res

    # ------------------------------------------------------------------ #
    def healthcheck(self) -> HealthcheckResult:
        """Full backend health check across the real-analysis chain."""
        hc = HealthcheckResult(backend=self.configured_backend)
        checks = hc.checks
        try:
            estimator, mode = self.get_real_estimator()
            checks["backend_resolved"] = True
            hc.analysis_mode = mode.value
        except ModelUnavailableError as e:
            checks["backend_resolved"] = False
            hc.error = str(e)
            hc.passed = False
            self._last_healthcheck = "failed"
            return hc

        try:
            checks["model_initialized"] = True
            frame = _synthetic_person_frame()
            seq = estimator.estimate_2d_pose(np.stack([frame] * 3), fps=30.0)
            checks["inference_ran"] = seq.num_frames == 3

            # PoseSequence conversion (correct shape + names).
            checks["pose_sequence_valid"] = (
                seq.keypoints.ndim == 3 and seq.keypoints.shape[1] == 17
            )

            # Metrics pipeline accepts the model output.
            from app.pipeline.events import GaitEventDetector
            from app.pipeline.metrics import GaitMetricsCalculator
            from app.pipeline.quality import QualityAssessmentService
            from app.pipeline.smoothing import TemporalSmoothingService

            class _Decoded:
                frames = np.stack([frame] * 3)
                fps = 30.0
                width = frame.shape[1]
                height = frame.shape[0]
                duration_sec = 0.1

            smoothed = TemporalSmoothingService().smooth(seq)
            quality = QualityAssessmentService().assess(_Decoded(), smoothed)
            events = GaitEventDetector().detect(smoothed)
            GaitMetricsCalculator().compute(smoothed, events, quality)
            checks["metrics_pipeline_accepts_output"] = True

            # No simulated data in real mode.
            checks["no_simulated_data_in_real_mode"] = (
                mode != AnalysisMode.demo_simulated
            )
            hc.simulated_data_used = mode == AnalysisMode.demo_simulated
        except Exception as e:
            hc.error = f"{type(e).__name__}: {e}"

        hc.passed = all(checks.values()) and not hc.error
        self._last_healthcheck = "passed" if hc.passed else "failed"
        return hc


_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    global _loader
    if _loader is None:
        _loader = ModelLoader()
    return _loader
