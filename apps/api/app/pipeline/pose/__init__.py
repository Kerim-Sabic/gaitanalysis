"""Pose estimation adapters.

The pipeline never imports a concrete model directly — it asks
``select_pose_estimator`` for an adapter that satisfies ``BasePoseEstimator``.
This keeps the system model-agnostic so MMPose/RTMPose, ViTPose++, WHAM, etc.
can be plugged in without touching the gait math.
"""
from .base import (
    COCO17_NAMES,
    LEFT_INDICES,
    RIGHT_INDICES,
    SKELETON_EDGES,
    BasePoseEstimator,
    KEYPOINT,
    PoseSequence,
)
from .factory import select_pose_estimator

__all__ = [
    "BasePoseEstimator",
    "PoseSequence",
    "COCO17_NAMES",
    "SKELETON_EDGES",
    "LEFT_INDICES",
    "RIGHT_INDICES",
    "KEYPOINT",
    "select_pose_estimator",
]
