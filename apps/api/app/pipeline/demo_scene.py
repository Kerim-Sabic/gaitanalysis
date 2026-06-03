"""Demo scene renderer.

For demo presets there is no real footage, so we render the simulated subject as
a neutral walking figure on a studio-gradient background. This gives the rest of
the pipeline *real frames* to assess (so video-quality scoring is genuine, not
faked) and yields a downloadable clip. The ``degrade`` flag reproduces a poor
capture (dark, blurred, noisy) so the "poor_quality" preset honestly scores low.

The clinical colour-coded skeleton overlay is drawn separately (overlay.py / the
frontend canvas); here we render a calm silhouette so the two are distinct.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.pose.base import SKELETON_EDGES, KEYPOINT
from app.pipeline.pose.simulated import GaitProfile
from app.pipeline.pose.base import PoseSequence

FIGURE = (172, 160, 140)   # BGR soft slate
BG_TOP = (74, 62, 52)
BG_BOTTOM = (124, 108, 94)


def _background(h: int, w: int) -> np.ndarray:
    grad = np.linspace(0, 1, h)[:, None]
    bg = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        bg[..., c] = (BG_TOP[c] + (BG_BOTTOM[c] - BG_TOP[c]) * grad).astype(np.uint8)
    # subtle floor line
    cv2.line(bg, (0, int(h * 0.82)), (w, int(h * 0.82)), (60, 50, 40), 2, cv2.LINE_AA)
    return bg


def render_scene(seq: PoseSequence, profile: GaitProfile) -> np.ndarray:
    h, w = seq.height, seq.width
    n = seq.num_frames
    base = _background(h, w)
    frames = np.empty((n, h, w, 3), dtype=np.uint8)
    kp = seq.keypoints
    rng = np.random.default_rng(3)

    thickness = max(2, int(0.012 * h))
    for i in range(n):
        img = base.copy()
        pts = kp[i, :, :2].astype(int)
        # torso fill
        torso = np.array([
            pts[KEYPOINT["left_shoulder"]], pts[KEYPOINT["right_shoulder"]],
            pts[KEYPOINT["right_hip"]], pts[KEYPOINT["left_hip"]],
        ], dtype=np.int32)
        cv2.fillConvexPoly(img, torso, (110, 102, 88), cv2.LINE_AA)
        for a, b in SKELETON_EDGES:
            cv2.line(img, tuple(pts[a]), tuple(pts[b]), FIGURE, thickness, cv2.LINE_AA)
        # head
        head_r = int(0.045 * h)
        cv2.circle(img, tuple(pts[KEYPOINT["nose"]]), head_r, FIGURE, -1, cv2.LINE_AA)

        if profile.degrade:
            small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_LINEAR)
            img = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
            img = cv2.GaussianBlur(img, (0, 0), 1.6)
            img = (img.astype(np.float32) * 0.5).astype(np.uint8)  # underexposed
            noise = rng.normal(0, 16, img.shape)
            img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        frames[i] = img
    return frames


def write_mp4(frames: np.ndarray, fps: float, out_path) -> bool:
    """Best-effort H.264 (avc1) then MPEG-4 fallback. Returns success."""
    h, w = frames.shape[1], frames.shape[2]
    for fourcc in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
        if writer.isOpened():
            for f in frames:
                writer.write(f)
            writer.release()
            return True
        writer.release()
    return False
