"""Real on-device 2D pose via the MediaPipe **Tasks** PoseLandmarker.

This is the MVP real backend. It uses the modern Tasks API (NOT the legacy
``mediapipe.solutions.pose``, which is absent from current MediaPipe builds) and
loads a local ``.task`` model file.

PoseLandmarker returns 33 BlazePose landmarks; we map to the canonical COCO-17
core AND preserve the foot landmarks (heel, foot_index) as extended keypoints —
these materially improve heel-strike / toe-off timing.

Model resolution order:
  1. explicit constructor path
  2. ``HORALIX_MEDIAPIPE_<VARIANT>_MODEL_PATH``
  3. ``HORALIX_MEDIAPIPE_MODEL_PATH`` (Full compatibility override)
  4. ``<repo>/models/pose/mediapipe/pose_landmarker_<variant>.task``

No landmarks are ever synthesized: frames without a detected pose are recorded
with zero confidence so downstream confidence/quality honestly degrade.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import REPO_ROOT

from .base import COCO17_NAMES, KEYPOINT, BasePoseEstimator, PoseModelInfo, PoseSequence

# BlazePose(33) -> COCO-17 core.
_BLAZE_TO_COCO = {
    "nose": 0,
    "left_eye": 2, "right_eye": 5,
    "left_ear": 7, "right_ear": 8,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}
EXTRA_LANDMARKS = [
    ("left_heel", 29), ("right_heel", 30),
    ("left_foot_index", 31), ("right_foot_index", 32),
]
EXTRA_NAMES = [name for name, _ in EXTRA_LANDMARKS]

SUPPORTED_VARIANTS = ("full", "heavy", "lite")


def resolve_model_path(variant: str = "full") -> Optional[Path]:
    variant = variant.lower()
    if variant not in SUPPORTED_VARIANTS:
        return None
    candidates: list[Path] = []
    variant_env = os.environ.get(f"HORALIX_MEDIAPIPE_{variant.upper()}_MODEL_PATH")
    if variant_env:
        candidates.append(Path(variant_env))
    if variant == "full":
        generic_env = os.environ.get("HORALIX_MEDIAPIPE_MODEL_PATH")
        if generic_env:
            candidates.append(Path(generic_env))
    filename = f"pose_landmarker_{variant}.task"
    candidates += [
        REPO_ROOT / "models" / "pose" / "mediapipe" / filename,
        REPO_ROOT / "apps" / "api" / "models" / "mediapipe" / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def tasks_import_error() -> Optional[str]:
    """Return None if the MediaPipe Tasks vision API is importable, else why not."""
    try:
        importlib.import_module("mediapipe")
        importlib.import_module("mediapipe.tasks.python")
        importlib.import_module("mediapipe.tasks.python.vision")
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def mediapipe_version() -> str:
    try:
        return importlib.import_module("mediapipe").__version__
    except Exception:
        return "unknown"


def detect_device() -> str:
    # MediaPipe Tasks runs on CPU (XNNPACK) by default in the Python package.
    return "cpu"


class MediaPipePoseEstimator(BasePoseEstimator):
    """MediaPipe Tasks PoseLandmarker adapter."""

    model_variant = "full"
    backend_id = "mediapipe_tasks_full"

    def __init__(self, model_path: Optional[str] = None,
                 min_pose_detection_confidence: float = 0.5, variant: Optional[str] = None):
        self.model_variant = (variant or self.model_variant).lower()
        self.backend_id = f"mediapipe_tasks_{self.model_variant}"
        self.model_path = Path(model_path) if model_path else resolve_model_path(self.model_variant)
        self.min_pose_detection_confidence = min_pose_detection_confidence
        self.device = detect_device()
        self.model_file = str(self.model_path) if self.model_path else ""

    # ------------------------------------------------------------------ #
    @classmethod
    def is_available(cls) -> bool:
        return tasks_import_error() is None and resolve_model_path(cls.model_variant) is not None

    @classmethod
    def availability_error(cls) -> Optional[str]:
        err = tasks_import_error()
        if err:
            return err
        if resolve_model_path(cls.model_variant) is None:
            return (
                f"MediaPipe Tasks {cls.model_variant} model file not found. Place "
                f"pose_landmarker_{cls.model_variant}.task under models/pose/mediapipe/."
            )
        return None

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name=f"MediaPipe Pose Landmarker {self.model_variant.title()} (Tasks)",
            version=mediapipe_version(),
            keypoint_format="COCO-17 + feet (heel, foot_index)",
            is_clinical_grade=False,
            notes=[
                f"Model file: {self.model_file or '(unresolved)'}.",
                f"Model variant: {self.model_variant}.",
                "Single-camera 2D pose; depth and out-of-plane motion are limited.",
                "Research/screening grade — clinical validation required.",
            ],
        )

    # ------------------------------------------------------------------ #
    def _build_landmarker(self):
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            PoseLandmarker,
            PoseLandmarkerOptions,
            RunningMode,
        )

        if not self.model_path or not self.model_path.exists():
            raise FileNotFoundError(
                "MediaPipe Tasks model (.task) not found. "
                "Set HORALIX_MEDIAPIPE_MODEL_PATH or add pose_landmarker_full.task."
            )
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=self.min_pose_detection_confidence,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return PoseLandmarker.create_from_options(options)

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        if tasks_import_error() is not None:
            raise RuntimeError(
                "Real pose model is unavailable. Run model setup or switch to Demo Mode. "
                f"({self.availability_error()})"
            )
        import cv2
        import mediapipe as mp

        n, h, w = int(frames.shape[0]), int(frames.shape[1]), int(frames.shape[2])
        core = np.zeros((n, 17, 3), dtype=np.float64)
        extra = np.zeros((n, len(EXTRA_LANDMARKS), 3), dtype=np.float64)
        fps = fps if fps and fps > 0 else 30.0

        landmarker = self._build_landmarker()
        try:
            last_ts = -1
            for i in range(n):
                rgb = cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                    data=np.ascontiguousarray(rgb))
                # Monotonically increasing timestamps in milliseconds.
                ts = int(round(i * 1000.0 / fps))
                if ts <= last_ts:
                    ts = last_ts + 1
                last_ts = ts
                result = landmarker.detect_for_video(mp_image, ts)
                if not result.pose_landmarks:
                    continue  # no pose this frame -> leave zeros (missing)
                lms = result.pose_landmarks[0]
                for name, bi in _BLAZE_TO_COCO.items():
                    lm = lms[bi]
                    core[i, KEYPOINT[name]] = [lm.x * w, lm.y * h, _score(lm)]
                for j, (_, bi) in enumerate(EXTRA_LANDMARKS):
                    lm = lms[bi]
                    extra[i, j] = [lm.x * w, lm.y * h, _score(lm)]
        finally:
            landmarker.close()

        t = np.arange(n) / fps
        return PoseSequence(
            keypoints=core, fps=fps, width=w, height=h, timestamps=t,
            names=list(COCO17_NAMES), extra_keypoints=extra, extra_names=list(EXTRA_NAMES),
        )


def _score(lm) -> float:
    """Confidence for a landmark: visibility, falling back to presence."""
    vis = float(getattr(lm, "visibility", 0.0) or 0.0)
    pres = float(getattr(lm, "presence", 0.0) or 0.0)
    return max(vis, pres) if (vis or pres) else 0.5


class MediaPipeFullPoseEstimator(MediaPipePoseEstimator):
    model_variant = "full"
    backend_id = "mediapipe_tasks_full"


class MediaPipeHeavyPoseEstimator(MediaPipePoseEstimator):
    model_variant = "heavy"
    backend_id = "mediapipe_tasks_heavy"
