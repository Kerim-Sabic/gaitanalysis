"""Segmentation adapters (SAM 2 person masking — optional, future)."""
from .base import BaseSegmenter, NullSegmenter
from .sam2_adapter import SAM2Segmenter

__all__ = ["BaseSegmenter", "NullSegmenter", "SAM2Segmenter"]
