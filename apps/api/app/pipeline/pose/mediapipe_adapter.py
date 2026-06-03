"""Real on-device 2D pose via MediaPipe (the first real working backend).

MediaPipe Pose (BlazePose) returns 33 landmarks. We remap to the canonical
COCO-17 layout (so the gait math is unchanged) AND additionally preserve the
foot landmarks (heel, foot_index) as *extended* keypoints — these materially
improve heel-strike / toe-off timing.

ROBUST AVAILABILITY
-------------------
``is_available()`` does **not** merely check ``import mediapipe`` — a hollow
build can import yet lack the inference engine. It confirms that
``mediapipe.solutions.pose.Pose`` is importable AND a real native binding is
present. This is what prevents fake "model loaded" states.

Install on a normal machine with::

    pip install mediapipe
"""
from __future__ import annotations

import importlib

import numpy as np

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

# Extended foot keypoints (BlazePose indices) appended after the COCO-17 core.
EXTRA_LANDMARKS = [
    ("left_heel", 29), ("right_heel", 30),
    ("left_foot_index", 31), ("right_foot_index", 32),
]
EXTRA_NAMES = [name for name, _ in EXTRA_LANDMARKS]


def _import_solutions_pose():
    """Return the real ``mediapipe.solutions.pose`` module or raise ImportError."""
    importlib.import_module("mediapipe")
    pose_mod = importlib.import_module("mediapipe.solutions.pose")
    if not hasattr(pose_mod, "Pose"):
        raise ImportError("mediapipe.solutions.pose has no 'Pose' (incomplete build)")
    # Confirm the native binding exists (hollow stubs lack mediapipe.python).
    importlib.import_module("mediapipe.python")
    return pose_mod


def mediapipe_version() -> str:
    try:
        return importlib.import_module("mediapipe").__version__
    except Exception:
        return "unknown"


def detect_device() -> str:
    # MediaPipe Python solutions run on CPU (XNNPACK) by default; a GPU delegate
    # is not enabled here. Report honestly.
    return "cpu"


class MediaPipePoseEstimator(BasePoseEstimator):
    def __init__(self, model_complexity: int = 1, min_detection_confidence: float = 0.5):
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.device = detect_device()

    @staticmethod
    def is_available() -> bool:
        try:
            _import_solutions_pose()
            return True
        except Exception:
            return False

    @staticmethod
    def availability_error() -> str | None:
        try:
            _import_solutions_pose()
            return None
        except Exception as e:  # surfaced to the model loader / status API
            return f"{type(e).__name__}: {e}"

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name="MediaPipe Pose (BlazePose)",
            version=mediapipe_version(),
            keypoint_format="COCO-17 + feet (heel, foot_index)",
            is_clinical_grade=False,
            notes=[
                "Single-camera 2D pose; depth and out-of-plane motion are limited.",
                "Research/screening grade — clinical validation required.",
            ],
        )

    def _new_pose(self):
        pose_mod = _import_solutions_pose()
        return pose_mod.Pose(
            static_image_mode=False,
            model_complexity=self.model_complexity,
            enable_segmentation=False,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=0.5,
        )

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        if not self.is_available():
            raise RuntimeError(
                "Real pose model is unavailable. Run model setup or switch to Demo Mode. "
                f"({self.availability_error()})"
            )
        n, h, w = frames.shape[0], frames.shape[1], frames.shape[2]
        core = np.zeros((n, 17, 3), dtype=np.float64)
        extra = np.zeros((n, len(EXTRA_LANDMARKS), 3), dtype=np.float64)
        pose = self._new_pose()
        try:
            for i in range(n):
                rgb = np.ascontiguousarray(frames[i][..., ::-1])  # BGR -> RGB
                res = pose.process(rgb)
                if not res.pose_landmarks:
                    continue
                lms = res.pose_landmarks.landmark
                for name, bi in _BLAZE_TO_COCO.items():
                    lm = lms[bi]
                    ci = KEYPOINT[name]
                    core[i, ci] = [lm.x * w, lm.y * h, float(getattr(lm, "visibility", 0.5))]
                for j, (_, bi) in enumerate(EXTRA_LANDMARKS):
                    lm = lms[bi]
                    extra[i, j] = [lm.x * w, lm.y * h, float(getattr(lm, "visibility", 0.5))]
        finally:
            pose.close()

        t = np.arange(n) / fps
        return PoseSequence(
            keypoints=core, fps=fps, width=w, height=h, timestamps=t,
            names=list(COCO17_NAMES), extra_keypoints=extra, extra_names=list(EXTRA_NAMES),
        )
