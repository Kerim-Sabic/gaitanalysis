"""Model loader — owns real-model selection, verification and health.

Hard rules:
  * Real analysis NEVER silently falls back to demo. If the configured real
    backend is unavailable, ``get_real_estimator`` raises ModelUnavailableError.
  * No fake success: verification is "passed" only when real landmarks are
    detected (on a real sample video). Inference that runs but detects no
    landmarks (e.g. synthetic frames, no sample present) is reported as
    "execution_only", never as full verification.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import REPO_ROOT, get_settings
from app.pipeline.pose.base import BasePoseEstimator
from app.schemas import AnalysisMode

from . import model_registry as registry
from .model_status import HealthcheckResult, ModelStatus, ModelVerifyResult

REAL_UNAVAILABLE_MSG = (
    "Real pose model is unavailable. Run model setup or switch to Demo Mode."
)
SAMPLE_VIDEO = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
VALID_FRAME_SCORE = 0.3


class ModelUnavailableError(Exception):
    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(REAL_UNAVAILABLE_MSG + (f" ({detail})" if detail else ""))


def _synthetic_person_frame(h: int = 480, w: int = 640) -> np.ndarray:
    import cv2

    img = np.full((h, w, 3), 60, np.uint8)
    cx = w // 2
    cv2.circle(img, (cx, 90), 34, (220, 200, 180), -1)
    cv2.rectangle(img, (cx - 35, 124), (cx + 35, 300), (200, 180, 160), -1)
    cv2.rectangle(img, (cx - 33, 300), (cx - 8, 450), (190, 170, 150), -1)
    cv2.rectangle(img, (cx + 8, 300), (cx + 33, 450), (190, 170, 150), -1)
    return img


class ModelLoader:
    def __init__(self):
        self._lock = threading.RLock()
        self._estimator: Optional[BasePoseEstimator] = None
        self._loaded_backend: Optional[str] = None
        self._init_error: Optional[str] = None
        self._last_healthcheck: str = "unknown"
        self._last_verify: Optional[ModelVerifyResult] = None

    @property
    def configured_backend(self) -> str:
        return registry.canonical(get_settings().pose_backend or "auto_best")

    # ------------------------------------------------------------------ #
    def get_real_estimator(self) -> tuple[BasePoseEstimator, AnalysisMode]:
        with self._lock:
            backend = registry.resolve_real_backend(self.configured_backend)
            if backend is None:
                detail = self._diagnose()
                self._init_error = detail
                raise ModelUnavailableError(detail)
            spec = registry.REGISTRY[backend]
            try:
                # Estimators hold mutable per-analysis selection/provenance state.
                # Return a fresh instance so concurrent upload jobs cannot leak
                # selected-backend metadata into one another.
                estimator = spec.adapter()
                self._estimator = estimator
                self._loaded_backend = backend
                self._init_error = None
                return estimator, spec.analysis_mode
            except Exception as e:  # pragma: no cover - defensive
                self._init_error = f"{type(e).__name__}: {e}"
                raise ModelUnavailableError(self._init_error) from e

    def _diagnose(self) -> str:
        pref = self.configured_backend
        if pref == "demo":
            return "HORALIX_POSE_BACKEND=demo: real analysis disabled (demo only)."
        spec = registry.REGISTRY.get(pref)
        if spec is None:
            return f"Unknown backend '{pref}'. Known: {registry.all_backend_names()}."
        if spec.kind != "real":
            return f"Backend '{pref}' is not a real backend."
        return spec.availability_error() or f"Backend '{pref}' reported unavailable."

    # ------------------------------------------------------------------ #
    def _sample_frames(self, max_frames: int = 30):
        """Return (frames, fps, source_label). Prefer the real sample video."""
        if SAMPLE_VIDEO.exists():
            from app.pipeline.video_processor import VideoProcessor

            decoded = VideoProcessor(max_frames=max_frames).load(SAMPLE_VIDEO, min_seconds=0.2)
            return decoded.frames, decoded.fps, str(SAMPLE_VIDEO)
        frame = _synthetic_person_frame()
        return np.stack([frame] * 3), 30.0, "synthetic"

    # ------------------------------------------------------------------ #
    def verify(self) -> ModelVerifyResult:
        res = ModelVerifyResult(backend=self.configured_backend)
        try:
            estimator, _mode = self.get_real_estimator()
        except ModelUnavailableError as e:
            res.error = str(e)
            res.status = "failed"
            self._last_verify = res
            return res

        info = estimator.get_model_info()
        res.model_name = info.name
        res.model_version = info.version
        res.model_file = getattr(estimator, "model_file", "")
        res.device = str(getattr(estimator, "device", "cpu"))
        try:
            frames, fps, source = self._sample_frames()
            res.sample_used = source
            res.initialized = True
            seq = estimator.estimate_2d_pose(frames, fps)
            res.backend = getattr(estimator, "selected_backend", "") or self._loaded_backend or res.backend
            info = estimator.get_model_info()
            res.model_name = info.name
            res.model_version = info.version
            res.model_file = getattr(estimator, "model_file", "")
            res.device = str(getattr(estimator, "device", "cpu"))
            res.inference_ran = True
            scores = seq.all_keypoints()[..., 2]
            res.landmark_count = int(seq.all_keypoints().shape[1])
            res.frames_processed = int(seq.num_frames)
            res.valid_pose_frames = int(np.sum(np.nanmean(scores, axis=1) > VALID_FRAME_SCORE))
            res.average_confidence = round(float(np.nanmean(scores)), 3) if scores.size else 0.0
            res.landmarks_detected = bool(np.any(scores > VALID_FRAME_SCORE))

            real_sample = source != "synthetic"
            if real_sample and res.landmarks_detected and res.valid_pose_frames > 0:
                res.status = "passed"
                res.passed = True
                res.note = "Real landmarks detected on the sample walking video."
            elif res.inference_ran:
                res.status = "execution_only"
                res.passed = False
                res.note = (
                    "Inference ran but full verification needs a real walking video at "
                    "data/sample_videos/walk_test.mp4 (no landmarks on synthetic input)."
                    if not real_sample else
                    "Inference ran on the sample but no confident landmarks were detected; "
                    "check video framing/quality."
                )
            else:
                res.status = "failed"
        except Exception as e:
            res.error = f"{type(e).__name__}: {e}"
            res.status = "failed"
        self._last_verify = res
        return res

    # ------------------------------------------------------------------ #
    def healthcheck(self) -> HealthcheckResult:
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
            hc.status = "failed"
            self._last_healthcheck = "failed"
            return hc

        try:
            checks["model_file_present"] = bool(getattr(estimator, "model_file", "")) or \
                mode == AnalysisMode.real_ultralytics_pose
            checks["model_initialized"] = True

            frames, fps, source = self._sample_frames()
            hc.sample_used = source
            seq = estimator.estimate_2d_pose(frames, fps)
            checks["model_file_present"] = bool(getattr(estimator, "model_file", "")) or \
                mode == AnalysisMode.real_ultralytics_pose
            selected_backend = getattr(estimator, "selected_backend", "") or self._loaded_backend or hc.backend
            mode = registry.analysis_mode_for_backend(selected_backend)
            hc.backend = selected_backend
            hc.analysis_mode = mode.value
            checks["inference_ran"] = seq.num_frames > 0
            checks["pose_sequence_valid"] = (
                seq.keypoints.ndim == 3 and seq.keypoints.shape[1] == 17
            )

            from types import SimpleNamespace

            from app.pipeline.events import GaitEventDetector
            from app.pipeline.metrics import GaitMetricsCalculator
            from app.pipeline.quality import QualityAssessmentService
            from app.pipeline.smoothing import TemporalSmoothingService

            decoded = SimpleNamespace(
                frames=frames, fps=fps, width=frames.shape[2], height=frames.shape[1],
                duration_sec=max(0.1, seq.num_frames / (fps or 30.0)),
            )
            smoothed = TemporalSmoothingService().smooth(seq)
            checks["smoothing_runs"] = True
            quality = QualityAssessmentService().assess(decoded, smoothed)
            events = GaitEventDetector().detect(smoothed)
            checks["events_run"] = True
            GaitMetricsCalculator().compute(smoothed, events, quality)
            checks["metrics_run"] = True

            scores = smoothed.all_keypoints()[..., 2]
            hc.valid_pose_frames = int(np.sum(np.nanmean(scores, axis=1) > VALID_FRAME_SCORE))
            checks["no_simulated_data_in_real_mode"] = mode != AnalysisMode.demo_simulated
            hc.simulated_data_used = mode == AnalysisMode.demo_simulated

            real_sample = source != "synthetic"
            if real_sample:
                checks["valid_pose_frames_present"] = hc.valid_pose_frames > 0
        except Exception as e:
            hc.error = f"{type(e).__name__}: {e}"

        core_ok = all(checks.values()) and not hc.error
        if core_ok and hc.sample_used != "synthetic":
            hc.status = "passed"
            hc.passed = True
        elif core_ok:
            hc.status = "execution_only"
            hc.passed = False
            hc.details.append(
                "Execution verified; full gait healthcheck needs a real walking video at "
                "data/sample_videos/walk_test.mp4."
            )
        else:
            hc.status = "failed"
            hc.passed = False
        self._last_healthcheck = hc.status
        return hc

    # ------------------------------------------------------------------ #
    def status(self) -> ModelStatus:
        with self._lock:
            configured = self.configured_backend
            configured_real = registry.resolve_real_backend(configured)
            available = registry.available_real_backends()
            name = version = model_file = ""
            device = "cpu"
            loaded = False
            init_err = None
            if configured == "demo":
                init_err = "HORALIX_POSE_BACKEND=demo: real analysis disabled (demo only)."
            elif configured_real:
                spec = registry.REGISTRY[configured_real]
                try:
                    est = spec.adapter()
                    info = est.get_model_info()
                    name, version = info.name, info.version
                    model_file = getattr(est, "model_file", "")
                    device = str(getattr(est, "device", "cpu"))
                    loaded = True
                except Exception as e:
                    init_err = f"{type(e).__name__}: {e}"
            else:
                spec = registry.REGISTRY.get(configured)
                init_err = spec.availability_error() if spec else f"Unknown backend '{configured}'."

            lv = self._last_verify
            return ModelStatus(
                configured_backend=configured,
                active_backend=configured_real or configured,
                available_backends=registry.all_backend_names(),
                configured_backend_available=bool(configured_real),
                any_real_backend_available=bool(available),
                demo_mode_available=get_settings().allow_demo_mode,
                real_analysis_available=bool(configured_real),
                model_loaded=loaded,
                model_verified=bool(lv and lv.passed),
                model_name=name,
                model_file=model_file,
                model_version=version,
                device=device,
                initialization_error=init_err,
                inference_test_status=(lv.status if lv else "not_run"),
                landmarks_detected=bool(lv and lv.landmarks_detected),
                landmark_count=(lv.landmark_count if lv else 0),
                valid_pose_frames=(lv.valid_pose_frames if lv else 0),
                average_confidence=(lv.average_confidence if lv else 0.0),
                last_healthcheck_status=self._last_healthcheck,
                simulated_data_used=False,
                backend_availability={
                    name: registry.is_real_backend_available(name)
                    for name, spec in registry.REGISTRY.items() if spec.kind == "real"
                },
                backend_errors={
                    name: (spec.availability_error() or "")
                    for name, spec in registry.REGISTRY.items()
                    if spec.kind == "real" and not registry.is_real_backend_available(name)
                },
            )


_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    global _loader
    if _loader is None:
        _loader = ModelLoader()
    return _loader
