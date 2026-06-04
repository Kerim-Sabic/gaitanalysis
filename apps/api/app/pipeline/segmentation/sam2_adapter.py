"""Strict SAM2 capability adapter.

Checkpoint presence is reported separately from verified video-mask inference.
Until prompted mask propagation and coordinate mapping are implemented, this
adapter fails clearly instead of reporting SAM2 as working.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

from app.config import REPO_ROOT

from .base import BaseSegmenter


class SAM2Segmenter(BaseSegmenter):
    def __init__(self, checkpoint: str | None = None, device: str = "cpu"):
        self.checkpoint = checkpoint or str(
            REPO_ROOT / "models" / "segmentation" / "sam2.1_hiera_tiny.pt"
        )
        self.device = device

    @staticmethod
    def is_available() -> bool:
        return False

    def availability_error(self) -> str:
        if importlib.util.find_spec("sam2") is None:
            return "Official SAM2 package is not installed."
        if not Path(self.checkpoint).exists():
            return f"SAM2 checkpoint missing: {self.checkpoint}"
        return "SAM2 prompted video-mask propagation is not yet integrated or verified."

    def segment_person(self, frames: np.ndarray) -> np.ndarray | None:
        raise RuntimeError(self.availability_error())
