"""Optional real SAM2.1 person-segmentation helper.

The adapter uses a local Ultralytics person box as the SAM2 prompt, then reports
capture-quality metadata. It is disabled by default and never returns fake
masks when the runtime, detector, or checkpoint is unavailable.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import time
from pathlib import Path

import numpy as np

from app.config import REPO_ROOT, get_settings

from .base import BaseSegmenter


class SAM2Segmenter(BaseSegmenter):
    model_name = "SAM2.1 Tiny"

    def __init__(self, checkpoint: str | None = None, device: str | None = None):
        self.checkpoint = Path(
            checkpoint
            or os.environ.get("HORALIX_SAM2_MODEL_PATH", "")
            or REPO_ROOT / "models" / "segmentation" / "sam2.1_hiera_tiny.pt"
        )
        self.detector_path = Path(
            os.environ.get("HORALIX_SAM2_DETECTOR_PATH", "")
            or REPO_ROOT / "models" / "pose" / "ultralytics" / "yolov8n-pose.pt"
        )
        self.config = os.environ.get(
            "HORALIX_SAM2_CONFIG", "configs/sam2.1/sam2.1_hiera_t.yaml"
        )
        self.device = device or ("cuda" if _cuda_available() else "cpu")
        self._predictor = None
        self._detector = None
        self.last_metadata: dict[str, object] = {}

    @classmethod
    def is_available(cls) -> bool:
        return cls().availability_error() is None

    def availability_error(self) -> str | None:
        if importlib.util.find_spec("sam2") is None:
            return (
                "BLOCKED_DEPENDENCY: official SAM2 package is not installed. "
                "Use apps/api/.venv-sam2 or the sam2 Docker profile."
            )
        if importlib.util.find_spec("ultralytics") is None:
            return "BLOCKED_DEPENDENCY: Ultralytics person-box prompt runtime is not installed."
        if not self.checkpoint.exists():
            return f"BLOCKED_WEIGHT: SAM2 checkpoint missing: {self.checkpoint}"
        if not self.detector_path.exists():
            return f"BLOCKED_WEIGHT: SAM2 person detector missing: {self.detector_path}"
        return None

    def _ensure_models(self):
        if self._predictor is not None and self._detector is not None:
            return self._predictor, self._detector
        error = self.availability_error()
        if error:
            raise RuntimeError(error)
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        from ultralytics import YOLO

        self._predictor = SAM2ImagePredictor(
            build_sam2(self.config, str(self.checkpoint), device=self.device)
        )
        self._detector = YOLO(str(self.detector_path))
        return self._predictor, self._detector

    def segment_person(self, frames: np.ndarray) -> np.ndarray | None:
        if frames.ndim != 4 or frames.shape[0] == 0:
            raise ValueError("SAM2 requires a non-empty (T,H,W,C) frame array.")
        predictor, detector = self._ensure_models()
        n, h, w = frames.shape[:3]
        limit = max(1, min(get_settings().sam2_max_frames, n))
        indices = np.unique(np.linspace(0, n - 1, limit).astype(int))
        masks = np.zeros((n, h, w), dtype=bool)
        boxes: list[np.ndarray] = []
        scores: list[float] = []
        started = time.perf_counter()

        for index in indices:
            frame = frames[index]
            result = detector.predict(frame, verbose=False, device=self.device)[0]
            if not len(result.boxes):
                continue
            best = int(np.argmax(result.boxes.conf.cpu().numpy()))
            box = result.boxes.xyxy[best].cpu().numpy().astype(np.float32)
            rgb = frame[..., ::-1].copy()
            predictor.set_image(rgb)
            predicted, mask_scores, _ = predictor.predict(
                box=box[None, :], multimask_output=False
            )
            mask = np.asarray(predicted[0], dtype=bool)
            if not mask.any():
                continue
            masks[index] = mask
            boxes.append(box)
            scores.append(float(mask_scores[0]))

        elapsed = time.perf_counter() - started
        if not boxes:
            raise RuntimeError("SAM2 inference ran, but no non-empty person mask was produced.")
        self.last_metadata = _metadata(masks, boxes, scores, elapsed, self)
        return masks

    def status(self) -> dict[str, object]:
        error = self.availability_error()
        return {
            "model": self.model_name,
            "dependency_version": _version("sam2"),
            "checkpoint_path": str(self.checkpoint),
            "config_path": self.config,
            "detector_path": str(self.detector_path),
            "device": self.device,
            "status": "WORKING" if self.last_metadata else (
                "AVAILABLE_NOT_ENABLED" if error is None else error.split(":", 1)[0]
            ),
            "error": error or "",
            **self.last_metadata,
        }


def _metadata(
    masks: np.ndarray,
    boxes: list[np.ndarray],
    scores: list[float],
    elapsed: float,
    segmenter: SAM2Segmenter,
) -> dict[str, object]:
    nonempty = np.asarray([mask.any() for mask in masks])
    selected = masks[nonempty]
    areas = selected.mean(axis=(1, 2))
    normalized_boxes = np.asarray(boxes, dtype=float)
    h, w = masks.shape[1:]
    normalized_boxes[:, [0, 2]] /= max(w, 1)
    normalized_boxes[:, [1, 3]] /= max(h, 1)
    centers = np.column_stack((
        (normalized_boxes[:, 0] + normalized_boxes[:, 2]) / 2,
        (normalized_boxes[:, 1] + normalized_boxes[:, 3]) / 2,
    ))
    sizes = np.column_stack((
        normalized_boxes[:, 2] - normalized_boxes[:, 0],
        normalized_boxes[:, 3] - normalized_boxes[:, 1],
    ))
    stability = max(0.0, 1.0 - float(np.std(centers)) - float(np.std(sizes)))
    full_body = float(np.mean(
        (normalized_boxes[:, 1] > 0.01) & (normalized_boxes[:, 3] < 0.995)
    ))
    feet_visible = []
    for mask, box in zip(selected, boxes):
        y1, y2 = int(max(0, box[1])), int(min(h, box[3]))
        x1, x2 = int(max(0, box[0])), int(min(w, box[2]))
        foot_y = y1 + int((y2 - y1) * 0.8)
        region = mask[foot_y:y2, x1:x2]
        feet_visible.append(float(region.mean()) if region.size else 0.0)
    return {
        "inference_verified": True,
        "frames_segmented": int(len(selected)),
        "mask_shape": list(selected[0].shape),
        "person_area_ratio": round(float(np.mean(areas)), 4),
        "bbox_stability": round(stability, 4),
        "feet_region_visibility_estimate": round(float(np.mean(feet_visible)), 4),
        "full_body_visibility_estimate": round(full_body, 4),
        "mean_mask_score": round(float(np.mean(scores)), 4),
        "processing_time_sec": round(elapsed, 4),
        "checkpoint_path": str(segmenter.checkpoint),
        "config_path": segmenter.config,
        "detector_path": str(segmenter.detector_path),
        "device": segmenter.device,
    }


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
        return "official-source"
