"""Segmenter interface. Person masks improve pose robustness against clutter and
background motion, and enable clean overlay compositing. Optional in the pipeline.
"""
from __future__ import annotations

import numpy as np


class BaseSegmenter:
    def segment_person(self, frames: np.ndarray) -> np.ndarray | None:
        """Return a ``(T, H, W)`` boolean mask for the primary subject, or None."""
        raise NotImplementedError

    @staticmethod
    def is_available() -> bool:
        return True


class NullSegmenter(BaseSegmenter):
    """No-op segmenter used when masking is disabled/unavailable."""

    def segment_person(self, frames: np.ndarray) -> np.ndarray | None:
        return None
