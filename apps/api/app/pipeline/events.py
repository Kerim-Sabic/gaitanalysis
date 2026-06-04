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

        hip_tracks = []
        for name in ("left_hip", "right_hip"):
            track = kp[:, KEYPOINT[name], 0].copy()
            track[kp[:, KEYPOINT[name], 2] < 0.2] = np.nan
            hip_tracks.append(track)
        hip_stack = np.stack(hip_tracks, axis=0)
        hip_count = np.sum(np.isfinite(hip_stack), axis=0)
        pelvis_x = np.divide(
            np.nansum(hip_stack, axis=0),
            hip_count,
            out=np.full(seq.num_frames, np.nan),
            where=hip_count > 0,
        )

        # Determine progression direction from net pelvis displacement.
        finite = np.isfinite(pelvis_x)
        sign = 1.0
        if finite.sum() > 2:
            valid_pelvis = pelvis_x[finite]
            edge = max(1, min(len(valid_pelvis) // 2, max(3, len(valid_pelvis) // 5)))
            disp = float(np.mean(valid_pelvis[-edge:]) - np.mean(valid_pelvis[:edge]))
            sign = 1.0 if disp >= 0 else -1.0

        result = EventSet(progression_axis="x", direction_sign=sign)
        # Minimum frames between heel strikes of the SAME foot (one stride).
        min_stride_s = 60.0 / (self.max_cadence / 2)
        min_dist = max(2, int(min_stride_s * fps * 0.6))

        for side in ("left", "right"):
            hs_track, hs_conf, hs_method = self._foot_track(
                seq, side, purpose="heel_strike"
            )
            to_track, to_conf, to_method = self._foot_track(
                seq, side, purpose="toe_off"
            )
            hs_rel = self._fill((hs_track - pelvis_x) * sign)
            to_rel = self._fill((to_track - pelvis_x) * sign)
            if not np.isfinite(hs_rel).any() or not np.isfinite(to_rel).any():
                result.notes.append(f"{side} foot/ankle not reliably tracked.")
                result.heel_strikes[side] = []
                result.toe_offs[side] = []
                continue

            hs_rel = hs_rel - np.nanmean(hs_rel)
            to_rel = to_rel - np.nanmean(to_rel)
            hs_prom = max(1.0, 0.25 * np.nanstd(hs_rel))
            to_prom = max(1.0, 0.25 * np.nanstd(to_rel))

            hs_idx, _ = find_peaks(hs_rel, distance=min_dist, prominence=hs_prom)
            to_idx, _ = find_peaks(-to_rel, distance=min_dist, prominence=to_prom)

            result.heel_strikes[side] = [float(t[i]) for i in hs_idx]
            result.toe_offs[side] = [float(t[i]) for i in to_idx]

            for i in hs_idx:
                result.events.append(GaitEvent(
                    type="heel_strike", side=side, frame_index=int(i),
                    timestamp=float(t[i]), confidence=float(hs_conf[i]),
                ))
            for i in to_idx:
                result.events.append(GaitEvent(
                    type="toe_off", side=side, frame_index=int(i),
                    timestamp=float(t[i]), confidence=float(to_conf[i]),
                ))
            result.notes.append(
                f"{side.title()} events use {hs_method} for heel strike and "
                f"{to_method} for toe off."
            )

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

    @staticmethod
    def _foot_track(
        seq: PoseSequence,
        side: str,
        *,
        purpose: str,
    ) -> tuple[np.ndarray, np.ndarray, str]:
        names = seq.all_names()
        all_kp = seq.all_keypoints()
        preferred = (
            [f"{side}_heel", f"{side}_ankle", f"{side}_foot_index"]
            if purpose == "heel_strike"
            else [f"{side}_foot_index", f"{side}_ankle", f"{side}_heel"]
        )
        available = [name for name in preferred if name in names]
        if not available:
            return (
                np.full(seq.num_frames, np.nan),
                np.zeros(seq.num_frames),
                "unavailable",
            )
        weights = np.asarray([0.50, 0.30, 0.20][:len(available)], dtype=float)
        points = np.stack([all_kp[:, names.index(name), 0] for name in available], axis=1)
        conf = np.stack([all_kp[:, names.index(name), 2] for name in available], axis=1)
        active_weights = weights[None, :] * (conf >= 0.2)
        denom = active_weights.sum(axis=1)
        track = np.divide(
            (points * active_weights).sum(axis=1),
            denom,
            out=np.full(seq.num_frames, np.nan),
            where=denom > 0,
        )
        method_factor = 1.0 if len(available) == 3 else (0.85 if len(available) == 2 else 0.65)
        event_conf = np.divide(
            (conf * active_weights).sum(axis=1),
            denom,
            out=np.zeros(seq.num_frames),
            where=denom > 0,
        ) * method_factor
        return track, np.clip(event_conf, 0.0, 1.0), " + ".join(available)
