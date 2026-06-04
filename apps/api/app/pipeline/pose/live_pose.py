"""Near-real-time single-frame pose for the live camera preview.

Uses a MediaPipe Tasks PoseLandmarker in IMAGE running mode (stateless per
frame) so the HTTP ``/live/frame`` endpoint can answer quickly. This is a
PREVIEW path for capture guidance — the recorded clip is still analysed by the
verified ``final_backend`` for the actual report. It never returns simulated
keypoints; if the live model is unavailable it raises clearly.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from app.config import get_settings

from .base import COCO17_NAMES
from .mediapipe_adapter import (
    EXTRA_LANDMARKS,
    EXTRA_NAMES,
    _BLAZE_TO_COCO,
    _score,
    mediapipe_version,
    resolve_model_path,
    tasks_import_error,
)
from .base import KEYPOINT

# Lower-body keypoints that must be visible for usable gait capture.
_FULL_BODY = ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]
_FEET = ["left_heel", "right_heel", "left_foot_index", "right_foot_index"]


class LivePoseUnavailable(Exception):
    pass


class LivePoseService:
    """Process-wide cached IMAGE-mode landmarker for the live preview."""

    def __init__(self):
        self._lock = threading.RLock()
        self._landmarker = None
        self._variant = ""

    # ------------------------------------------------------------------ #
    def _backend(self) -> str:
        b = (get_settings().live_backend or "mediapipe_tasks_full").lower()
        return "heavy" if b.endswith("heavy") else "full"

    def available_error(self) -> Optional[str]:
        err = tasks_import_error()
        if err:
            return err
        if resolve_model_path(self._backend()) is None:
            return (
                f"Live model file not found (pose_landmarker_{self._backend()}.task). "
                "Place it under models/pose/mediapipe/ or set HORALIX_MEDIAPIPE_MODEL_PATH."
            )
        return None

    def is_available(self) -> bool:
        return self.available_error() is None

    def status(self) -> dict:
        variant = self._backend()
        return {
            "available": self.is_available(),
            "backend": f"mediapipe_tasks_{variant}",
            "model_variant": variant,
            "model_version": mediapipe_version(),
            "model_file": str(resolve_model_path(variant) or ""),
            "error": self.available_error(),
            "keypoint_source": "real_video_inference",
            "simulated_data_used": False,
        }

    # ------------------------------------------------------------------ #
    def _ensure(self):
        variant = self._backend()
        if self._landmarker is not None and self._variant == variant:
            return self._landmarker
        err = self.available_error()
        if err:
            raise LivePoseUnavailable(err)
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            PoseLandmarker,
            PoseLandmarkerOptions,
            RunningMode,
        )

        model_path = resolve_model_path(variant)
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=get_settings().live_min_detection_confidence,
            min_pose_presence_confidence=0.4,
        )
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
        self._landmarker = PoseLandmarker.create_from_options(options)
        self._variant = variant
        return self._landmarker

    def infer_frame(self, bgr: np.ndarray, frame_index: int = 0) -> dict:
        """Run single-frame pose. Returns keypoints + confidence + warnings.
        Thread-safe (serialised) so one cached model serves the latest frame."""
        import cv2
        import mediapipe as mp

        h, w = int(bgr.shape[0]), int(bgr.shape[1])
        with self._lock:
            landmarker = self._ensure()
            t0 = time.perf_counter()
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            result = landmarker.detect(mp_image)
            infer_ms = round((time.perf_counter() - t0) * 1000.0, 1)

        names = list(COCO17_NAMES) + list(EXTRA_NAMES)
        kpts = [[0.0, 0.0, 0.0] for _ in names]
        conf_by_name: dict[str, float] = {}
        valid_pose = False
        if result.pose_landmarks:
            lms = result.pose_landmarks[0]
            for name, bi in _BLAZE_TO_COCO.items():
                lm = lms[bi]
                s = _score(lm)
                kpts[KEYPOINT[name]] = [round(lm.x * w, 1), round(lm.y * h, 1), round(s, 3)]
                conf_by_name[name] = s
            for off, (nm, bi) in enumerate(EXTRA_LANDMARKS):
                lm = lms[bi]
                s = _score(lm)
                kpts[17 + off] = [round(lm.x * w, 1), round(lm.y * h, 1), round(s, 3)]
                conf_by_name[nm] = s
            valid_pose = True

        mean_conf = round(float(np.mean([c for c in conf_by_name.values()])), 3) if conf_by_name else 0.0
        warnings = self._coach(conf_by_name, valid_pose)
        return {
            "frame_index": frame_index,
            "timestamp": round(time.time(), 3),
            "width": w,
            "height": h,
            "keypoints": kpts,
            "keypoint_names": names,
            "valid_pose": valid_pose,
            "mean_confidence": mean_conf,
            "left_leg_visible": min(conf_by_name.get("left_hip", 0), conf_by_name.get("left_ankle", 0)) > 0.4,
            "right_leg_visible": min(conf_by_name.get("right_hip", 0), conf_by_name.get("right_ankle", 0)) > 0.4,
            "feet_visible": any(conf_by_name.get(n, 0) > 0.4 for n in _FEET),
            "inference_ms": infer_ms,
            "backend": f"mediapipe_tasks_{self._backend()}",
            "keypoint_source": "real_video_inference",
            "simulated_data_used": False,
            "warnings": warnings,
            "good_capture": valid_pose and not warnings,
        }

    @staticmethod
    def _coach(conf: dict, valid_pose: bool) -> list[str]:
        if not valid_pose:
            return ["No person detected — step into frame, side-on, full body visible."]
        msgs: list[str] = []
        if any(conf.get(n, 0) < 0.4 for n in _FULL_BODY):
            msgs.append("Step back until your full body (hips, knees, ankles) is in frame.")
        if not any(conf.get(n, 0) > 0.4 for n in _FEET):
            msgs.append("Feet are not clearly visible — keep heels/toes in frame.")
        mean_lower = np.mean([conf.get(n, 0) for n in _FULL_BODY]) if conf else 0
        if mean_lower < 0.5:
            msgs.append("Low tracking confidence — improve lighting and reduce background clutter.")
        return msgs


_service: Optional[LivePoseService] = None


def get_live_pose_service() -> LivePoseService:
    global _service
    if _service is None:
        _service = LivePoseService()
    return _service
