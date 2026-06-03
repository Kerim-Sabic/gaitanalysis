"""MMPose / RTMPose / RTMW3D adapter (placeholder with a real integration path).

This is the recommended *clinical-research-grade* 2D/3D backend. It is left as a
clearly-marked placeholder so the heavy ``torch`` + ``mmcv`` + ``mmpose`` stack
is not a hard dependency. The integration points are spelled out below and in
docs/architecture.md.

To enable:
    1. pip install -U openmim && mim install mmengine mmcv mmpose
    2. Download an RTMPose body checkpoint (COCO-17 or COCO-WholeBody-133).
    3. Set HORALIX_POSE_BACKEND=mmpose and fill in the TODOs.
"""
from __future__ import annotations

import numpy as np

from .base import BasePoseEstimator, PoseModelInfo, PoseSequence


def _mmpose_available() -> bool:
    try:
        import mmpose  # noqa: F401

        return True
    except Exception:
        return False


class MMPosePoseEstimator(BasePoseEstimator):
    """Adapter for MMPose top-down RTMPose / RTMW3D models."""

    def __init__(self, config: str | None = None, checkpoint: str | None = None,
                 device: str = "cpu"):
        self.config = config
        self.checkpoint = checkpoint
        self.device = device
        self._inferencer = None

    @staticmethod
    def is_available() -> bool:
        return _mmpose_available()

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name="MMPose RTMPose",
            version="(configure checkpoint)",
            keypoint_format="COCO-17 / COCO-WholeBody-133",
            is_clinical_grade=False,
            notes=["Research-grade; clinical validation per docs/validation_plan.md required."],
        )

    def _ensure_model(self):
        if self._inferencer is not None:
            return
        from mmpose.apis import MMPoseInferencer  # type: ignore

        # RTMPose body model with built-in person detection.
        self._inferencer = MMPoseInferencer(
            pose2d=self.config or "rtmpose-m_8xb256-420e_body8-256x192",
            device=self.device,
        )

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        if not self.is_available():
            raise RuntimeError(
                "MMPose is not installed. Install it or use HORALIX_POSE_BACKEND=auto."
            )
        self._ensure_model()
        n, h, w = frames.shape[0], frames.shape[1], frames.shape[2]
        kp = np.zeros((n, 17, 3), dtype=np.float64)
        # TODO: batch through self._inferencer and pick the dominant track.
        # The MMPoseInferencer yields dict(predictions=[[instance,...]]) per frame
        # where instance.keypoints is (17,2) and instance.keypoint_scores is (17,).
        for i, result in enumerate(self._inferencer(list(frames), show=False)):
            preds = result["predictions"][0]
            if not preds:
                continue
            inst = max(preds, key=lambda p: float(np.mean(p["keypoint_scores"])))
            kp[i, :, :2] = np.asarray(inst["keypoints"])[:17]
            kp[i, :, 2] = np.asarray(inst["keypoint_scores"])[:17]
        from .base import COCO17_NAMES

        t = np.arange(n) / fps
        return PoseSequence(
            keypoints=kp, fps=fps, width=w, height=h, timestamps=t, names=list(COCO17_NAMES)
        )
