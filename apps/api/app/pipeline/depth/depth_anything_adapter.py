"""Optional real Depth Anything V2 relative-depth helper.

Output is relative scene metadata only. It is never used as calibrated clinical
distance or substituted for camera calibration.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

import numpy as np

from app.config import REPO_ROOT, get_settings

LIMITATION = (
    "Depth Anything V2 produces relative monocular depth, not calibrated clinical distance."
)

MODEL_CONFIGS = {
    "vits": {"encoder": "vits", "features": 64, "out_channels": [48, 96, 192, 384]},
    "vitb": {"encoder": "vitb", "features": 128, "out_channels": [96, 192, 384, 768]},
    "vitl": {"encoder": "vitl", "features": 256, "out_channels": [256, 512, 1024, 1024]},
}


class DepthAnythingV2Adapter:
    def __init__(self, checkpoint: str | None = None, device: str | None = None):
        self.checkpoint = Path(
            checkpoint
            or os.environ.get("HORALIX_DEPTH_MODEL_PATH", "")
            or REPO_ROOT / "models" / "depth" / "Depth-Anything-V2-Small"
            / "depth_anything_v2_vits.pth"
        )
        self.source = Path(
            os.environ.get("HORALIX_DEPTH_SOURCE", "")
            or REPO_ROOT / ".runtime" / "depth-anything-v2"
        )
        self.device = device or ("cuda" if _cuda_available() else "cpu")
        self.encoder = next(
            (name for name in MODEL_CONFIGS if f"_{name}." in self.checkpoint.name),
            "vits",
        )
        self._model = None
        self.last_metadata: dict[str, object] = {}

    def _add_source(self) -> None:
        if self.source.exists() and str(self.source) not in sys.path:
            sys.path.insert(0, str(self.source))

    @classmethod
    def is_available(cls) -> bool:
        return cls().availability_error() is None

    def availability_error(self) -> str | None:
        if not self.checkpoint.exists():
            return f"BLOCKED_WEIGHT: missing checkpoint: {self.checkpoint}"
        self._add_source()
        if importlib.util.find_spec("depth_anything_v2") is None:
            return (
                f"BLOCKED_DEPENDENCY: official Depth Anything V2 source not found at "
                f"{self.source}. Clone https://github.com/DepthAnything/Depth-Anything-V2."
            )
        if importlib.util.find_spec("torch") is None:
            return "BLOCKED_DEPENDENCY: torch is not installed."
        return None

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        error = self.availability_error()
        if error:
            raise RuntimeError(error)
        import torch
        from depth_anything_v2.dpt import DepthAnythingV2

        model = DepthAnythingV2(**MODEL_CONFIGS[self.encoder])
        model.load_state_dict(torch.load(self.checkpoint, map_location="cpu"))
        self._model = model.to(self.device).eval()
        return self._model

    def estimate_relative_depth(self, frames: np.ndarray) -> np.ndarray:
        if frames.ndim != 4 or frames.shape[0] == 0:
            raise ValueError("Depth Anything V2 requires a non-empty (T,H,W,C) frame array.")
        model = self._ensure_model()
        n = frames.shape[0]
        limit = max(1, min(get_settings().depth_max_frames, n))
        indices = np.unique(np.linspace(0, n - 1, limit).astype(int))
        outputs = []
        started = time.perf_counter()
        for index in indices:
            outputs.append(np.asarray(model.infer_image(frames[index]), dtype=np.float32))
        elapsed = time.perf_counter() - started
        depths = np.stack(outputs)
        if not np.isfinite(depths).all() or float(np.ptp(depths)) <= 0:
            raise RuntimeError("Depth inference ran but returned an invalid relative-depth map.")
        self.last_metadata = {
            "inference_verified": True,
            "frames_processed": int(len(depths)),
            "output_shape": list(depths.shape),
            "relative_depth_min": round(float(depths.min()), 5),
            "relative_depth_median": round(float(np.median(depths)), 5),
            "relative_depth_max": round(float(depths.max()), 5),
            "relative_depth_std": round(float(depths.std()), 5),
            "processing_time_sec": round(elapsed, 4),
            "checkpoint_path": str(self.checkpoint),
            "source_path": str(self.source),
            "device": self.device,
            "limitation": LIMITATION,
        }
        return depths

    def status(self) -> dict[str, object]:
        error = self.availability_error()
        return {
            "model": "Depth Anything V2",
            "checkpoint_path": str(self.checkpoint),
            "source_path": str(self.source),
            "device": self.device,
            "status": "WORKING" if self.last_metadata else (
                "AVAILABLE_NOT_ENABLED" if error is None else error.split(":", 1)[0]
            ),
            "error": error or "",
            **self.last_metadata,
        }


def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False
