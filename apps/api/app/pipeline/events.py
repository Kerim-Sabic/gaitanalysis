"""Gait-event detection.

Method: coordinate-based event detection (Zeni et al., Gait & Posture 2008) — a
validated markerless-compatible approach for sagittal video.

  * Define the pelvis/sacrum centre as the midpoint of the hips.
  * For each foot, take the ankle's position in the direction of progression,
    relative to the pelvis: ``rel = ankle_x - pelvis_x`` (sign-normalised so the
    subject moves in +x).
  * Heel strike  ≈ local MAXIMA of ``rel`` (foot most anterior).
  * Toe off      ≈ local MINIMA of ``rel`` (foot most posterior).

When COCO-WholeBody heel/toe points are unavailable we use the ankle as a proxy;
this is recorded as a limitation. Peak spacing is constrained by the expected
cadence to suppress spurious detections.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import find_peaks

from app.pipeline.pose.base import KEYPOINT, PoseSequence
from app.schemas import GaitEvent


@dataclass
class EventSet:
    events: list[GaitEvent] = field(default_factory=list)
    progression_axis: str = "x"
    direction_sign: float = 1.0
    heel_strikes: dict[str, list[float]] = field(default_factory=dict)  # side -> times
    toe_offs: dict[str, list[float]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class GaitEventDetector:
    def __init__(self, min_cadence_spm: float = 40.0, max_cadence_spm: float = 200.0):
        self.min_cadence = min_cadence_spm
        self.max_cadence = max_cadence_spm

    def detect(self, seq: PoseSequence) -> EventSet:
        fps = seq.fps
        t = seq.timestamps
        kp = seq.keypoints

        pelvis_x = np.nanmean(
            [kp[:, KEYPOINT["left_hip"], 0], kp[:, KEYPOINT["right_hip"], 0]], axis=0
        )

        # Determine progression direction from net pelvis displacement.
        finite = np.isfinite(pelvis_x)
        sign = 1.0
        if finite.sum() > 2:
            disp = np.nanmean(pelvis_x[-max(3, finite.sum() // 5):]) - np.nanmean(
                pelvis_x[: max(3, finite.sum() // 5)]
            )
            sign = 1.0 if disp >= 0 else -1.0

        result = EventSet(progression_axis="x", direction_sign=sign)
        # Minimum frames between heel strikes of the SAME foot (one stride).
        min_stride_s = 60.0 / (self.max_cadence / 2)
        min_dist = max(2, int(min_stride_s * fps * 0.6))

        for side in ("left", "right"):
            ankle_x = kp[:, KEYPOINT[f"{side}_ankle"], 0]
            rel = (ankle_x - pelvis_x) * sign
            rel = self._fill(rel)
            if not np.isfinite(rel).any():
                result.notes.append(f"{side} ankle not reliably tracked.")
                result.heel_strikes[side] = []
                result.toe_offs[side] = []
                continue

            rel = rel - np.nanmean(rel)
            prom = max(1.0, 0.25 * np.nanstd(rel))

            hs_idx, _ = find_peaks(rel, distance=min_dist, prominence=prom)
            to_idx, _ = find_peaks(-rel, distance=min_dist, prominence=prom)

            result.heel_strikes[side] = [float(t[i]) for i in hs_idx]
            result.toe_offs[side] = [float(t[i]) for i in to_idx]

            for i in hs_idx:
                result.events.append(GaitEvent(
                    type="heel_strike", side=side, frame_index=int(i),
                    timestamp=float(t[i]), confidence=float(kp[i, KEYPOINT[f"{side}_ankle"], 2]),
                ))
            for i in to_idx:
                result.events.append(GaitEvent(
                    type="toe_off", side=side, frame_index=int(i),
                    timestamp=float(t[i]), confidence=float(kp[i, KEYPOINT[f"{side}_ankle"], 2]),
                ))

        result.events.sort(key=lambda e: e.timestamp)
        return result

    @staticmethod
    def _fill(arr: np.ndarray) -> np.ndarray:
        a = arr.copy()
        idx = np.arange(len(a))
        good = np.isfinite(a)
        if good.sum() >= 2:
            a = np.interp(idx, idx[good], a[good])
        return a
