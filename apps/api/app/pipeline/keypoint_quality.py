"""Keypoint tracking-quality analysis.

Turns a (smoothed) ``PoseSequence`` into per-keypoint quality statistics and
provides the logic that derives **metric confidence from keypoint quality** (so
confidence is never generic). Color thresholds are mirrored in
``packages/shared/src/keypoints.ts`` for the frontend.

Tracking-confidence bands (shared with the UI):
    GREEN  >= 0.80  reliable tracking
    YELLOW >= 0.60  moderate confidence
    ORANGE >= 0.40  low confidence / possible occlusion
    RED     < 0.40  unreliable or missing
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.pipeline.pose.base import PoseSequence
from app.schemas import KeypointStat

GOOD_T = 0.80
MODERATE_T = 0.60
LIMITED_T = 0.40
VISIBLE_T = 0.50   # "confidently tracked" for valid-frame coverage
MISSING_T = 0.20   # below this the keypoint is effectively missing

# Which metrics each keypoint contributes to (drives "related metrics" + the
# confidence_reason wording).
RELATED_METRICS: dict[str, list[str]] = {
    "left_ankle": ["cadence_steps_per_min", "left_step_time_sec", "left_stride_time_sec",
                   "step_time_asymmetry", "walking_speed_m_per_s", "knee_rom_left_deg"],
    "right_ankle": ["cadence_steps_per_min", "right_step_time_sec", "right_stride_time_sec",
                    "step_time_asymmetry", "walking_speed_m_per_s", "knee_rom_right_deg"],
    "left_heel": ["cadence_steps_per_min", "left_step_time_sec", "stance_time_asymmetry"],
    "right_heel": ["cadence_steps_per_min", "right_step_time_sec", "stance_time_asymmetry"],
    "left_foot_index": ["left_step_time_sec", "stance_time_asymmetry"],
    "right_foot_index": ["right_step_time_sec", "stance_time_asymmetry"],
    "left_knee": ["knee_rom_left_deg", "knee_rom_asymmetry"],
    "right_knee": ["knee_rom_right_deg", "knee_rom_asymmetry"],
    "left_hip": ["hip_rom_left_deg", "walking_speed_m_per_s", "cadence_steps_per_min"],
    "right_hip": ["hip_rom_right_deg", "walking_speed_m_per_s", "cadence_steps_per_min"],
    "left_shoulder": ["trunk_sway_index"],
    "right_shoulder": ["trunk_sway_index"],
    "nose": ["trunk_sway_index"],
}


def quality_band(conf: float) -> str:
    if conf >= GOOD_T:
        return "good"
    if conf >= MODERATE_T:
        return "moderate"
    if conf >= LIMITED_T:
        return "limited"
    return "unreliable"


def keypoint_side(name: str) -> str:
    if name.startswith("left_"):
        return "left"
    if name.startswith("right_"):
        return "right"
    return "midline"


def _note(band: str, missing_pct: float) -> str:
    if band == "good":
        return "Tracking appears reliable."
    if band == "moderate":
        return "Moderate tracking — usable with caution."
    if band == "limited":
        return ("Low confidence or partial occlusion — likely foot/limb hidden, "
                "motion blur, or oblique angle.")
    if missing_pct > 25:
        return "Frequently missing — metrics using this point are unreliable."
    return "Unreliable tracking — interpret related metrics with caution."


def compute_keypoint_stats(seq: PoseSequence) -> list[KeypointStat]:
    kps = seq.all_keypoints()           # (T, K, 3)
    names = seq.all_names()
    T = kps.shape[0]
    mask = seq.interpolated_mask
    stats: list[KeypointStat] = []
    for i, name in enumerate(names):
        scores = kps[:, i, 2]
        mean_c = float(np.nanmean(scores)) if scores.size else 0.0
        valid = float(np.mean(scores >= VISIBLE_T)) * 100.0
        missing = float(np.mean(scores < MISSING_T)) * 100.0
        interp = 0.0
        if mask is not None and mask.shape[1] > i:
            interp = float(np.mean(mask[:, i])) * 100.0
        band = quality_band(mean_c)
        stats.append(KeypointStat(
            name=name, side=keypoint_side(name), index=i,
            mean_confidence=round(mean_c, 3),
            valid_frame_percent=round(valid, 1),
            missing_frame_percent=round(missing, 1),
            interpolated_percent=round(interp, 1),
            quality_band=band,
            related_metrics=RELATED_METRICS.get(name, []),
            note=_note(band, missing),
        ))
    return stats


@dataclass
class KeypointQualityIndex:
    """Fast lookup of per-keypoint quality for metric-confidence derivation."""

    by_name: dict[str, KeypointStat]

    @classmethod
    def from_stats(cls, stats: list[KeypointStat]) -> "KeypointQualityIndex":
        return cls({s.name: s for s in stats})

    def mean_conf(self, names: list[str]) -> float:
        vals = [self.by_name[n].mean_confidence for n in names if n in self.by_name]
        return float(np.mean(vals)) if vals else 0.0

    def min_valid_pct(self, names: list[str]) -> float:
        vals = [self.by_name[n].valid_frame_percent for n in names if n in self.by_name]
        return float(min(vals)) if vals else 0.0

    def max_interp_pct(self, names: list[str]) -> float:
        vals = [self.by_name[n].interpolated_percent for n in names if n in self.by_name]
        return float(max(vals)) if vals else 0.0

    def metric_confidence(
        self,
        source_keypoints: list[str],
        *,
        quality_score: float,
        calibration_factor: float = 1.0,
        event_consistency: float = 1.0,
    ) -> tuple[float, str]:
        """Confidence in [0,1] derived from the source keypoints' tracking
        quality, valid-frame coverage, interpolation, video quality and (where
        relevant) calibration. Returns ``(confidence, reason)``."""
        present = [n for n in source_keypoints if n in self.by_name]
        if not present:
            return 0.3, "No directly-tracked keypoints available for this metric."
        kp_conf = self.mean_conf(present)
        valid = self.min_valid_pct(present) / 100.0
        interp = self.max_interp_pct(present) / 100.0
        q = max(0.0, min(1.0, quality_score / 100.0))

        conf = (0.45 * kp_conf + 0.25 * valid + 0.15 * q + 0.15 * event_consistency)
        conf *= (1.0 - 0.4 * interp)          # interpolation penalty
        conf *= calibration_factor            # e.g. speed without calibration
        conf = float(max(0.0, min(1.0, conf)))

        worst = min(present, key=lambda n: self.by_name[n].mean_confidence)
        reason = (
            f"{', '.join(n.replace('_', ' ') for n in present[:4])} visible across "
            f"{self.min_valid_pct(present):.0f}% of frames "
            f"(mean conf {kp_conf:.0%}"
            + (f", {interp*100:.0f}% interpolated" if interp > 0.02 else "")
            + (f"; weakest: {worst.replace('_', ' ')}" if self.by_name[worst].mean_confidence < 0.6 else "")
            + ")."
        )
        return round(conf, 3), reason
