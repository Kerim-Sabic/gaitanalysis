"""MMPose RTMW adapter with strict dependency/config/checkpoint validation.

RTMW checkpoints are not self-describing. A matching config is mandatory; the
adapter refuses to guess a config/checkpoint pairing and reports the blocker.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import REPO_ROOT

from .base import COCO17_NAMES, BasePoseEstimator, PoseModelInfo, PoseSequence

RTMW_WEIGHTS = [
    "models/pose/rtmw/rtmw-x_simcc-cocktail14_pt-ucoco_270e-384x288-f840f204_20231122.pth",
    "models/pose/rtmw/rtmw-dw-x-l_simcc-cocktail14_270e-384x288-20231122.pth",
    "models/pose/rtmw/rtmw-x_simcc-cocktail14_pt-ucoco_270e-256x192-13a2546d_20231208.pth",
]
RTMW3D_WEIGHTS = [
    "models/pose/rtmw3d/rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.pth",
    "models/pose/rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth",
]
WHOLEBODY_EXTRA = [
    ("left_foot_index", 17),
    ("left_small_toe", 18),
    ("left_heel", 19),
    ("right_foot_index", 20),
    ("right_small_toe", 21),
    ("right_heel", 22),
]
EXTRA_NAMES = [name for name, _ in WHOLEBODY_EXTRA]


def _import_error() -> Optional[str]:
    missing = []
    for module in ("torch", "mmengine", "mmcv", "mmpose"):
        try:
            importlib.import_module(module)
        except Exception as exc:
            missing.append(f"{module}: {type(exc).__name__}: {exc}")
    return "; ".join(missing) if missing else None


def _first_existing(paths: list[str]) -> Optional[Path]:
    return next((REPO_ROOT / path for path in paths if (REPO_ROOT / path).exists()), None)


def resolve_rtmw_checkpoint() -> Optional[Path]:
    env = os.environ.get("HORALIX_MMPPOSE_CHECKPOINT")
    return Path(env) if env and Path(env).exists() else _first_existing(RTMW_WEIGHTS)


def resolve_rtmw_config() -> Optional[Path]:
    env = os.environ.get("HORALIX_MMPPOSE_CONFIG")
    if env and Path(env).exists():
        return Path(env)
    config_dir = REPO_ROOT / "models" / "pose" / "rtmw" / "configs"
    if config_dir.exists():
        return next(iter(sorted(config_dir.rglob("*.py"))), None)
    return None


class MMPoseRTMWPoseEstimator(BasePoseEstimator):
    backend_id = "mmpose_rtmw"

    def __init__(
        self,
        config: str | None = None,
        checkpoint: str | None = None,
        device: str | None = None,
    ):
        self.config = Path(config) if config else resolve_rtmw_config()
        self.checkpoint = Path(checkpoint) if checkpoint else resolve_rtmw_checkpoint()
        self.device = device or ("cuda:0" if _cuda_available() else "cpu")
        self.model_file = str(self.checkpoint or "")
        self._inferencer = None

    @classmethod
    def is_available(cls) -> bool:
        return (
            _import_error() is None
            and resolve_rtmw_config() is not None
            and resolve_rtmw_checkpoint() is not None
        )

    @classmethod
    def availability_error(cls) -> Optional[str]:
        err = _import_error()
        if err:
            return err
        if resolve_rtmw_checkpoint() is None:
            return "RTMW checkpoint missing under models/pose/rtmw/."
        if resolve_rtmw_config() is None:
            return (
                "Matching RTMW config missing. Set HORALIX_MMPPOSE_CONFIG or place the "
                "matching OpenMMLab config under models/pose/rtmw/configs/."
            )
        return None

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name="MMPose RTMW WholeBody",
            version=_version("mmpose"),
            keypoint_format="COCO-17 + RTMW whole-body feet when emitted",
            notes=[
                f"Config: {self.config or '(missing)'}.",
                f"Checkpoint: {self.checkpoint or '(missing)'}.",
                "Research-grade; matching config/checkpoint and clinical validation are required.",
            ],
        )

    def _ensure_model(self):
        if self._inferencer is not None:
            return self._inferencer
        error = self.availability_error()
        if error:
            raise RuntimeError(error)
        from mmpose.apis import MMPoseInferencer  # type: ignore

        self._inferencer = MMPoseInferencer(
            pose2d=str(self.config),
            pose2d_weights=str(self.checkpoint),
            device=self.device,
        )
        return self._inferencer

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        inferencer = self._ensure_model()
        n, h, w = frames.shape[0], frames.shape[1], frames.shape[2]
        core = np.zeros((n, 17, 3), dtype=np.float64)
        extra = np.zeros((n, len(WHOLEBODY_EXTRA), 3), dtype=np.float64)
        for i, result in enumerate(inferencer(list(frames), show=False, return_vis=False)):
            if i >= n:
                break
            predictions = result.get("predictions", [[]])
            instances = predictions[0] if predictions else []
            if not instances:
                continue
            inst = max(instances, key=lambda item: float(np.mean(item["keypoint_scores"])))
            points = np.asarray(inst["keypoints"], dtype=float)
            scores = np.asarray(inst["keypoint_scores"], dtype=float)
            count = min(17, len(points), len(scores))
            core[i, :count, :2] = points[:count, :2]
            core[i, :count, 2] = scores[:count]
            for j, (_, source_index) in enumerate(WHOLEBODY_EXTRA):
                if source_index < len(points) and source_index < len(scores):
                    extra[i, j, :2] = points[source_index, :2]
                    extra[i, j, 2] = scores[source_index]
        fps = fps if fps > 0 else 30.0
        return PoseSequence(
            keypoints=core,
            extra_keypoints=extra,
            extra_names=list(EXTRA_NAMES),
            fps=fps,
            width=w,
            height=h,
            timestamps=np.arange(n) / fps,
            names=list(COCO17_NAMES),
        )


class MMPoseRTMW3DPoseEstimator(BasePoseEstimator):
    backend_id = "mmpose_rtmw3d"

    def __init__(self):
        self.checkpoint = _first_existing(RTMW3D_WEIGHTS)
        self.model_file = str(self.checkpoint or "")
        self.device = "cuda:0" if _cuda_available() else "cpu"

    @staticmethod
    def is_available() -> bool:
        return False

    @staticmethod
    def availability_error() -> str:
        weight = _first_existing(RTMW3D_WEIGHTS)
        if not weight:
            return "RTMW3D checkpoint missing."
        return (
            "RTMW3D checkpoint is present, but the matching config and verified 3D "
            "PoseSequence mapping are not installed. Use the MMPose Docker profile."
        )

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name="MMPose RTMW3D",
            version="blocked",
            keypoint_format="RTMW3D",
            notes=[self.availability_error()],
        )

    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        raise RuntimeError(self.availability_error())


# Compatibility alias used by the existing health endpoint.
MMPosePoseEstimator = MMPoseRTMWPoseEstimator


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _version(module: str) -> str:
    try:
        return str(importlib.import_module(module).__version__)
    except Exception:
        return "unknown"
