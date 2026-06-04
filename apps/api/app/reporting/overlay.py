"""Server-side skeleton overlay video renderer (OpenCV).

Draws the smoothed skeleton (left/right colour-coded), keypoints scaled by
confidence, a bounding box and gait-event markers onto the source frames (or a
dark canvas in pure-demo mode) and writes an MP4.

The frontend also renders an *interactive* canvas overlay from the pose-track
JSON; this server-side render is for download/sharing and headless reports.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.pipeline.pose.base import SKELETON_EDGES
from app.pipeline.video_processor import VideoProcessor
from app.schemas import GaitAnalysisResult, PoseTrack

LEFT_COLOR = (235, 180, 52)    # BGR amber  -> left
RIGHT_COLOR = (235, 110, 45)   # BGR blue   -> right
MID_COLOR = (200, 200, 200)
EVENT_COLOR = (90, 220, 90)


def _edge_color(a: int, left_idx: list[int]) -> tuple[int, int, int]:
    if a in left_idx:
        return LEFT_COLOR
    return RIGHT_COLOR


def render_overlay_video(
    pose: PoseTrack,
    result: GaitAnalysisResult,
    out_path: str | Path,
    source_video_path: str | None = None,
) -> Path:
    out_path = Path(out_path)
    fps = pose.fps or 30.0
    w, h = pose.width, pose.height

    frames = None
    if source_video_path and Path(source_video_path).exists():
        decoded = VideoProcessor().load(source_video_path, min_seconds=0.1)
        frames = decoded.frames
        h, w = frames.shape[1], frames.shape[2]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

    event_frames = {e.frame_index: e for e in result.events}
    left_set = set(pose.left_indices)
    n = min(len(pose.frames), frames.shape[0] if frames is not None else len(pose.frames))

    for i in range(n):
        canvas = (frames[i].copy() if frames is not None
                  else np.full((h, w, 3), 18, dtype=np.uint8))
        if frames is None:
            canvas[:] = (26, 22, 18)  # dark navy-ish

        kpts = pose.frames[i].keypoints
        # edges
        for a, b in SKELETON_EDGES:
            xa, ya, sa = kpts[a]
            xb, yb, sb = kpts[b]
            if sa < 0.2 or sb < 0.2:
                continue
            col = _edge_color(a, list(left_set))
            cv2.line(canvas, (int(xa), int(ya)), (int(xb), int(yb)), col, 2, cv2.LINE_AA)
        # keypoints
        for j, (x, y, s) in enumerate(kpts):
            if s < 0.2:
                continue
            r = 3 + int(3 * s)
            col = LEFT_COLOR if j in left_set else RIGHT_COLOR
            cv2.circle(canvas, (int(x), int(y)), r, col, -1, cv2.LINE_AA)

        # HUD
        cv2.putText(canvas, f"Horalix Gait AI  ·  frame {i}  ·  conf {pose.frames[i].mean_confidence:.2f}",
                    (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
        if result.simulated_data_used:
            cv2.putText(canvas, "DEMO - simulated keypoints, not real patient analysis",
                        (12, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 180, 250), 1, cv2.LINE_AA)
        # event marker
        if i in event_frames:
            ev = event_frames[i]
            cv2.putText(canvas, f"{ev.type} ({ev.side})", (12, 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, EVENT_COLOR, 2, cv2.LINE_AA)
            cv2.circle(canvas, (w - 24, 24), 10, EVENT_COLOR, -1, cv2.LINE_AA)

        writer.write(canvas)

    writer.release()
    return out_path
