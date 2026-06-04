"""Strict optional Depth Anything V2 capability check.

Monocular depth is relative and must not be used as calibrated clinical distance.
"""
from __future__ import annotations

import importlib.util

from app.config import REPO_ROOT

LIMITATION = (
    "Monocular depth is relative and should not be used as calibrated clinical distance."
)


class DepthAnythingV2Adapter:
    checkpoint = REPO_ROOT / "models/depth/Depth-Anything-V2-Large/depth_anything_v2_vitl.pth"

    @classmethod
    def is_available(cls) -> bool:
        return False

    @classmethod
    def availability_error(cls) -> str | None:
        if not cls.checkpoint.exists():
            return f"Missing checkpoint: {cls.checkpoint}"
        if importlib.util.find_spec("depth_anything_v2") is None:
            return "Depth Anything V2 runtime/source package is not installed."
        return "Depth Anything V2 inference has not been verified in this pipeline."

    def estimate_relative_depth(self, frames):
        raise RuntimeError(self.availability_error() or "Depth inference is not integrated.")
