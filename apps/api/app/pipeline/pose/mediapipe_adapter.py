"""Real on-device 2D pose via MediaPipe (optional dependency).

MediaPipe Pose returns 33 BlazePose landmarks; we remap them to the canonical
COCO-17 layout so the rest of the pipeline is unchanged. Install with::

    pip install mediapipe

If the package is missing this adapter reports ``is_available() == False`` and
the factory falls back to the simulated estimator.
"""
from __future__ import annotations

import numpy as np

from .base import COCO17_NAMES, KEYPOINT, BasePoseEstimator, PoseModelInfo, PoseSequence

# BlazePose (33) -> COCO-17 mapping.
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


def _mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401

        return True
    except Exception:
        return False


class MediaPipePoseEstimator(BasePoseEstimator):
    def __init__(self, model_complexity: int = 1):
        self.model_complexity = model_complexity

    @staticmethod
    def is_available() -> bool:
        return _mediapipe_available()

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name="MediaPipe BlazePose",
            version="0.10.x",
            keypoint_format="COCO-17 (remapped from BlazePose-33)",
            is_clinical_grade=False,
            notes=[
                "Single-camera 2D pose; depth and out-of-plane motion are limited.",
                "Research/screening grade — clinical validation required.",
            ],
        )

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        import mediapipe as mp

        n, h, w = frames.shape[0], frames.shape[1], frames.shape[2]
        kp = np.zeros((n, 17, 3), dtype=np.float64)
        pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=self.model_complexity,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        try:
            for i in range(n):
                rgb = frames[i][..., ::-1]  # BGR -> RGB
                res = pose.process(np.ascontiguousarray(rgb))
                if not res.pose_landmarks:
                    continue
                lms = res.pose_landmarks.landmark
                for name, blaze_idx in _BLAZE_TO_COCO.items():
                    lm = lms[blaze_idx]
                    ci = KEYPOINT[name]
                    kp[i, ci, 0] = lm.x * w
                    kp[i, ci, 1] = lm.y * h
                    kp[i, ci, 2] = float(getattr(lm, "visibility", 0.5))
        finally:
            pose.close()

        t = np.arange(n) / fps
        return PoseSequence(
            keypoints=kp, fps=fps, width=w, height=h, timestamps=t, names=list(COCO17_NAMES)
        )
