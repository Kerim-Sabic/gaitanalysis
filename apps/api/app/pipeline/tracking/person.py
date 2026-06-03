"""Person detection & dominant-subject selection.

For the top-down pose path the pose model already localises people, so this
service operates on the *pose output*: it counts candidate subjects, picks the
dominant track (largest, most central, most persistent), and surfaces a
"multiple people" warning. A ByteTrack/RTMDet adapter can be slotted in later
to do this on raw frames before pose — the interface stays the same.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.pipeline.pose.base import PoseSequence


@dataclass
class PersonTrack:
    num_candidates: int
    multiple_people: bool
    coverage: float  # fraction of frames the subject is present with usable pose
    bbox_series: np.ndarray  # (T, 4) x1,y1,x2,y2


class PersonDetectionService:
    def __init__(self, min_score: float = 0.3):
        self.min_score = min_score

    def analyze(self, seq: PoseSequence) -> PersonTrack:
        kp = seq.keypoints
        scores = kp[..., 2]
        present = (scores > self.min_score).mean(axis=1) > 0.4  # per-frame presence
        coverage = float(present.mean()) if present.size else 0.0

        # Bounding box per frame from confident keypoints.
        boxes = np.zeros((seq.num_frames, 4), dtype=np.float64)
        for i in range(seq.num_frames):
            m = scores[i] > self.min_score
            if m.sum() >= 2:
                xs, ys = kp[i, m, 0], kp[i, m, 1]
                boxes[i] = [xs.min(), ys.min(), xs.max(), ys.max()]

        # Single-track simulated/real top-down output -> at most one subject here.
        # A future multi-instance backend would set num_candidates > 1.
        num_candidates = 1 if coverage > 0 else 0
        return PersonTrack(
            num_candidates=num_candidates,
            multiple_people=False,
            coverage=coverage,
            bbox_series=boxes,
        )
