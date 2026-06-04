"""Regression check: richer foot landmarks raise event provenance/confidence."""
from __future__ import annotations

import numpy as np

import _bootstrap  # noqa: F401

from app.pipeline.events import GaitEventDetector
from app.pipeline.pose.base import COCO17_NAMES, KEYPOINT, PoseSequence


def sequence(with_feet: bool) -> PoseSequence:
    fps, n, width, height = 30.0, 180, 1280, 720
    t = np.arange(n) / fps
    kp = np.zeros((n, 17, 3), dtype=float)
    pelvis = 300 + 40 * t
    for side, phase in (("left", 0.0), ("right", np.pi)):
        for name in ("hip", "knee", "ankle"):
            idx = KEYPOINT[f"{side}_{name}"]
            kp[:, idx, 0] = pelvis + (35 if name == "ankle" else 0) * np.sin(2 * np.pi * t + phase)
            kp[:, idx, 1] = {"hip": 330, "knee": 470, "ankle": 620}[name]
            kp[:, idx, 2] = 0.8
    extra = None
    names = []
    if with_feet:
        names = ["left_heel", "right_heel", "left_foot_index", "right_foot_index"]
        extra = np.zeros((n, 4, 3), dtype=float)
        for i, phase in enumerate((0.0, np.pi, 0.0, np.pi)):
            extra[:, i, 0] = pelvis + 40 * np.sin(2 * np.pi * t + phase)
            extra[:, i, 1] = 625
            extra[:, i, 2] = 0.8
    return PoseSequence(
        keypoints=kp, extra_keypoints=extra, extra_names=names,
        fps=fps, width=width, height=height, timestamps=t, names=list(COCO17_NAMES),
    )


def main() -> int:
    detector = GaitEventDetector()
    ankle_only = detector.detect(sequence(False))
    with_feet = detector.detect(sequence(True))
    ankle_conf = float(np.mean([event.confidence for event in ankle_only.events]))
    feet_conf = float(np.mean([event.confidence for event in with_feet.events]))
    assert ankle_only.events and with_feet.events
    assert feet_conf > ankle_conf
    assert any("foot_index" in note for note in with_feet.notes)
    assert any("ankle" in note for note in ankle_only.notes)
    print(f"ankle-only event confidence: {ankle_conf:.3f}")
    print(f"foot-aware event confidence: {feet_conf:.3f}")
    print("STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
