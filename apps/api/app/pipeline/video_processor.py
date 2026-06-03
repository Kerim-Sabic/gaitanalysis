"""Video loading, validation and frame extraction (real, OpenCV-based)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

SUPPORTED_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


class VideoError(Exception):
    """Raised for unreadable / unsupported / too-short video."""


@dataclass
class DecodedVideo:
    frames: np.ndarray  # (T, H, W, 3) BGR, uint8 — possibly downsampled
    fps: float
    width: int
    height: int
    frame_count: int
    duration_sec: float
    rotation: int = 0
    sampled_stride: int = 1
    metadata: dict = field(default_factory=dict)


class VideoProcessor:
    """Loads a video, reads metadata, and extracts a normalized frame stack.

    To keep memory bounded on long clips we cap the analysed frames and the long
    edge; ``sampled_stride`` records any temporal subsampling so timestamps stay
    correct downstream.
    """

    def __init__(self, max_frames: int = 900, max_long_edge: int = 960):
        self.max_frames = max_frames
        self.max_long_edge = max_long_edge

    def probe(self, path: str | Path) -> dict:
        path = Path(path)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise VideoError(f"Unsupported file type: {path.suffix}")
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise VideoError("Could not open video (corrupt or unsupported codec).")
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            rotation = int(cap.get(cv2.CAP_PROP_ORIENTATION_META)) if hasattr(
                cv2, "CAP_PROP_ORIENTATION_META"
            ) else 0
        finally:
            cap.release()
        duration = (frame_count / fps) if fps > 0 else 0.0
        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "rotation": rotation,
            "duration_sec": duration,
        }

    def load(self, path: str | Path, min_seconds: float = 2.0) -> DecodedVideo:
        path = Path(path)
        meta = self.probe(path)
        fps = meta["fps"] if meta["fps"] > 0 else 30.0

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise VideoError("Could not open video for decoding.")

        # Decide stride so total analysed frames <= max_frames.
        total = meta["frame_count"]
        stride = max(1, int(np.ceil(total / self.max_frames))) if total else 1

        frames: list[np.ndarray] = []
        idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if idx % stride == 0:
                    frame = self._apply_rotation(frame, meta["rotation"])
                    frame = self._resize(frame)
                    frames.append(frame)
                idx += 1
        finally:
            cap.release()

        if not frames:
            raise VideoError("No frames could be decoded from the video.")

        stack = np.stack(frames, axis=0)
        eff_fps = fps / stride
        duration = (idx / fps) if fps > 0 else (len(frames) / eff_fps)
        if duration < min_seconds:
            raise VideoError(
                f"Video too short ({duration:.1f}s). At least {min_seconds:.0f}s is required."
            )

        h, w = stack.shape[1], stack.shape[2]
        return DecodedVideo(
            frames=stack,
            fps=eff_fps,
            width=w,
            height=h,
            frame_count=len(frames),
            duration_sec=duration,
            rotation=meta["rotation"],
            sampled_stride=stride,
            metadata=meta,
        )

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        long_edge = max(h, w)
        if long_edge <= self.max_long_edge:
            return frame
        scale = self.max_long_edge / long_edge
        return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _apply_rotation(frame: np.ndarray, rotation: int) -> np.ndarray:
        if rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        if rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        if rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame
