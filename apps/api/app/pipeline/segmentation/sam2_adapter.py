"""SAM 2 person-masking adapter (placeholder with integration path).

SAM 2 provides temporally-consistent video object masks. Combined with the
person detector's first-frame box prompt, it yields a stable subject mask across
occlusions. Install ``segment-anything-2`` and a checkpoint, then implement the
TODO. Until then this reports unavailable and the pipeline uses NullSegmenter.
"""
from __future__ import annotations

import numpy as np

from .base import BaseSegmenter


def _sam2_available() -> bool:
    try:
        import sam2  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


class SAM2Segmenter(BaseSegmenter):
    def __init__(self, checkpoint: str | None = None, device: str = "cpu"):
        self.checkpoint = checkpoint
        self.device = device

    @staticmethod
    def is_available() -> bool:
        return _sam2_available()

    def segment_person(self, frames: np.ndarray) -> np.ndarray | None:
        if not self.is_available():
            return None
        # TODO: build SAM2 video predictor, prompt with the detector box on frame 0,
        # propagate, and return the boolean mask volume.
        raise NotImplementedError("SAM2 integration pending — see docs/architecture.md")
