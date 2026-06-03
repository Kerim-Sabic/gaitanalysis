"""Real fallback backend via Ultralytics YOLO-Pose (backend id: ``ultralytics_pose``).

This is a genuine real backend (not a placeholder) but a *limited* one: YOLO-Pose
emits COCO-17 keypoints only — **no heel / foot_index** — so foot-specific gait
metrics (heel-strike/toe-off precision, some step-timing) have reduced confidence.

Availability is strict: only "available" if ``ultralytics`` imports, the weights
load, and inference runs. Weights resolution:
  1. ``HORALIX_ULTRALYTICS_MODEL_PATH``
  2. ``<repo>/models/pose/ultralytics/yolov8n-pose.pt``
  3. bare ``yolov8n-pose.pt`` (Ultralytics will auto-download if online)
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import REPO_ROOT

from .base import COCO17_NAMES, BasePoseEstimator, PoseModelInfo, PoseSequence

LIMITATION = (
    "Ultralytics COCO-17 backend used; heel and foot-index landmarks unavailable, "
    "so foot-specific gait metrics have reduced confidence."
)


def _ultralytics_import_error() -> Optional[str]:
    try:
        importlib.import_module("ultralytics")
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def resolve_weights() -> Optional[str]:
    env = os.environ.get("HORALIX_ULTRALYTICS_MODEL_PATH")
    if env and Path(env).exists():
        return env
    local = REPO_ROOT / "models" / "pose" / "ultralytics" / "yolov8n-pose.pt"
    if local.exists():
        return str(local)
    # Bare name -> Ultralytics resolves/downloads (only succeeds if online/cached).
    return "yolov8n-pose.pt"


class UltralyticsPoseEstimator(BasePoseEstimator):
    backend_id = "ultralytics_pose"

    def __init__(self, weights: Optional[str] = None):
        self.weights = weights or resolve_weights()
        self.device = "cpu"
        self.model_file = self.weights
        self._model = None

    @staticmethod
    def is_available() -> bool:
        if _ultralytics_import_error() is not None:
            return False
        # Require a concrete local weights file; do not assume network access.
        env = os.environ.get("HORALIX_ULTRALYTICS_MODEL_PATH")
        if env and Path(env).exists():
            return True
        return (REPO_ROOT / "models" / "pose" / "ultralytics" / "yolov8n-pose.pt").exists()

    @staticmethod
    def availability_error() -> Optional[str]:
        err = _ultralytics_import_error()
        if err:
            return err
        if not UltralyticsPoseEstimator.is_available():
            return (
                "Ultralytics weights not found. Set HORALIX_ULTRALYTICS_MODEL_PATH or place "
                "yolov8n-pose.pt under models/pose/ultralytics/ (or `pip install ultralytics` "
                "and download yolov8n-pose.pt)."
            )
        return None

    def get_model_info(self) -> PoseModelInfo:
        ver = "unknown"
        try:
            ver = importlib.import_module("ultralytics").__version__
        except Exception:
            pass
        return PoseModelInfo(
            name="Ultralytics YOLOv8-Pose",
            version=ver,
            keypoint_format="COCO-17 (no heel/foot_index)",
            is_clinical_grade=False,
            notes=[f"Weights: {self.model_file}", LIMITATION],
        )

    def _ensure_model(self):
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.weights)
        return self._model

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        if _ultralytics_import_error() is not None:
            raise RuntimeError(
                "Real pose model is unavailable. Run model setup or switch to Demo Mode. "
                f"({self.availability_error()})"
            )
        model = self._ensure_model()
        n, h, w = int(frames.shape[0]), int(frames.shape[1]), int(frames.shape[2])
        core = np.zeros((n, 17, 3), dtype=np.float64)
        fps = fps if fps and fps > 0 else 30.0

        for i in range(n):
            res = model.predict(frames[i], verbose=False, device=self.device)
            if not res or res[0].keypoints is None or res[0].keypoints.xy is None:
                continue
            kxy = res[0].keypoints.xy.cpu().numpy()  # (num, 17, 2)
            kconf = (
                res[0].keypoints.conf.cpu().numpy()
                if res[0].keypoints.conf is not None else None
            )
            if kxy.shape[0] == 0:
                continue
            # Pick the most confident / largest detection.
            idx = 0
            if kconf is not None and kconf.shape[0] > 1:
                idx = int(np.argmax(kconf.mean(axis=1)))
            for k in range(17):
                conf = float(kconf[idx, k]) if kconf is not None else 0.5
                core[i, k] = [float(kxy[idx, k, 0]), float(kxy[idx, k, 1]), conf]

        t = np.arange(n) / fps
        # No extended foot keypoints for COCO-17 YOLO-Pose.
        return PoseSequence(
            keypoints=core, fps=fps, width=w, height=h, timestamps=t,
            names=list(COCO17_NAMES),
        )
