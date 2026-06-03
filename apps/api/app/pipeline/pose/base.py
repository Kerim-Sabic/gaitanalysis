"""Pose estimator interface and the canonical keypoint convention.

We standardise on the COCO-17 layout because every mainstream 2D pose model
(RTMPose, ViTPose, MediaPipe-mapped, OpenPose-mapped) can emit it. Foot
keypoints (heel/big-toe) from COCO-WholeBody are *optional* — when absent the
gait-event detector degrades gracefully using the ankle as a proxy and the
limitation is recorded in the report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# Canonical COCO-17 ordering.
COCO17_NAMES: list[str] = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

# Named index lookup, e.g. KEYPOINT["left_ankle"] -> 15
KEYPOINT: dict[str, int] = {name: i for i, name in enumerate(COCO17_NAMES)}

SKELETON_EDGES: list[list[int]] = [
    [5, 7], [7, 9],            # left arm
    [6, 8], [8, 10],           # right arm
    [5, 6],                    # shoulders
    [5, 11], [6, 12],          # torso sides
    [11, 12],                  # pelvis
    [11, 13], [13, 15],        # left leg
    [12, 14], [14, 16],        # right leg
    [0, 5], [0, 6],            # neck-ish
]

LEFT_INDICES: list[int] = [1, 3, 5, 7, 9, 11, 13, 15]
RIGHT_INDICES: list[int] = [2, 4, 6, 8, 10, 12, 14, 16]


@dataclass
class PoseSequence:
    """Keypoints over time.

    ``keypoints`` has shape ``(num_frames, 17, 3)`` where the last axis is
    ``(x, y, score)`` in pixel coordinates (origin top-left, y increasing down).
    """

    keypoints: np.ndarray  # (T, 17, 3)
    fps: float
    width: int
    height: int
    timestamps: np.ndarray  # (T,)
    names: list[str] = field(default_factory=lambda: list(COCO17_NAMES))

    @property
    def num_frames(self) -> int:
        return int(self.keypoints.shape[0])

    @property
    def mean_confidence(self) -> float:
        scores = self.keypoints[..., 2]
        return float(np.nanmean(scores)) if scores.size else 0.0

    def joint(self, name: str) -> np.ndarray:
        """Return the (T, 3) track for a named keypoint."""
        return self.keypoints[:, KEYPOINT[name], :]

    def copy(self) -> "PoseSequence":
        return PoseSequence(
            keypoints=self.keypoints.copy(),
            fps=self.fps,
            width=self.width,
            height=self.height,
            timestamps=self.timestamps.copy(),
            names=list(self.names),
        )


@dataclass
class PoseModelInfo:
    name: str
    version: str
    keypoint_format: str = "COCO-17"
    is_clinical_grade: bool = False
    notes: list[str] = field(default_factory=list)


class BasePoseEstimator:
    """Abstract adapter every pose backend implements."""

    def get_model_info(self) -> PoseModelInfo:  # pragma: no cover - interface
        raise NotImplementedError

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        """Estimate 2D keypoints for a stack of ``(T, H, W, 3)`` BGR frames."""
        raise NotImplementedError

    def estimate_3d_pose(self, frames: np.ndarray, fps: float) -> Optional[PoseSequence]:
        """Optional 3D lifting. Returns ``None`` when unsupported."""
        return None

    @staticmethod
    def is_available() -> bool:
        return True
