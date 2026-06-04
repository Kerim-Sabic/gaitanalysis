"""Quality-first comparison of real pose backend outputs."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.pipeline.events import GaitEventDetector

from .base import PoseSequence

VALID_FRAME_SCORE = 0.30


def _joint_confidence(seq: PoseSequence, names: list[str]) -> float:
    all_names = seq.all_names()
    all_kp = seq.all_keypoints()
    idx = [all_names.index(name) for name in names if name in all_names]
    return float(np.nanmean(all_kp[:, idx, 2])) if idx else 0.0


def _jitter_stability(seq: PoseSequence) -> float:
    if seq.num_frames < 3:
        return 0.0
    kp = seq.keypoints
    xy = kp[..., :2].copy()
    xy[kp[..., 2] < 0.25] = np.nan
    speed = np.linalg.norm(np.diff(xy, axis=0), axis=2) / max(seq.width, seq.height, 1)
    finite = speed[np.isfinite(speed)]
    if not finite.size:
        return 0.0
    return float(np.clip(1.0 - float(np.nanmedian(finite)) / 0.08, 0.0, 1.0))


def _event_consistency(seq: PoseSequence) -> float:
    events = GaitEventDetector().detect(seq)
    left = len(events.heel_strikes.get("left", []))
    right = len(events.heel_strikes.get("right", []))
    total = left + right
    if total < 2:
        return 0.2
    balance = 1.0 - abs(left - right) / max(total, 1)
    coverage = min(1.0, total / max(2.0, seq.num_frames / max(seq.fps, 1.0)))
    return float(np.clip(0.55 * balance + 0.45 * coverage, 0.0, 1.0))


def score_pose_sequence(
    seq: PoseSequence,
    *,
    backend: str,
    inference_time_sec: float = 0.0,
) -> dict[str, Any]:
    """Return transparent quality features and a 0..100 final score."""
    scores = seq.all_keypoints()[..., 2]
    frame_means = np.nanmean(scores, axis=1) if scores.size else np.asarray([])
    valid_pct = float(np.mean(frame_means > VALID_FRAME_SCORE) * 100.0) if frame_means.size else 0.0
    mean_conf = float(np.nanmean(scores)) if scores.size else 0.0
    hip = _joint_confidence(seq, ["left_hip", "right_hip"])
    knee = _joint_confidence(seq, ["left_knee", "right_knee"])
    ankle = _joint_confidence(seq, ["left_ankle", "right_ankle"])
    heel = _joint_confidence(seq, ["left_heel", "right_heel"])
    foot = _joint_confidence(seq, ["left_foot_index", "right_foot_index"])
    foot_available = all(
        name in seq.all_names()
        for name in ("left_heel", "right_heel", "left_foot_index", "right_foot_index")
    )
    missing_pct = float(np.mean(scores < 0.20) * 100.0) if scores.size else 100.0
    interp_pct = (
        float(np.mean(seq.interpolated_mask) * 100.0)
        if seq.interpolated_mask is not None and seq.interpolated_mask.size else 0.0
    )
    stability = _jitter_stability(seq)
    event_consistency = _event_consistency(seq)
    metric_completeness = float(np.mean([
        hip > 0.25, knee > 0.25, ankle > 0.25, valid_pct >= 40,
        event_consistency >= 0.4,
    ]))
    foot_quality = float(np.mean([ankle, heel, foot])) if foot_available else ankle * 0.55
    time_penalty = min(5.0, inference_time_sec / max(seq.num_frames, 1) * 30.0)
    final = (
        0.30 * valid_pct + 24.0 * mean_conf + 18.0 * foot_quality
        + 10.0 * stability + 8.0 * event_consistency + 10.0 * metric_completeness
        - 0.08 * missing_pct - 0.04 * interp_pct - time_penalty
    )
    if not foot_available:
        final -= 4.0
    return {
        "backend": backend,
        "final_score": round(float(np.clip(final, 0.0, 100.0)), 3),
        "valid_pose_percentage": round(valid_pct, 3),
        "average_confidence": round(mean_conf, 4),
        "hip_confidence": round(hip, 4),
        "knee_confidence": round(knee, 4),
        "ankle_confidence": round(ankle, 4),
        "heel_confidence": round(heel, 4),
        "foot_index_confidence": round(foot, 4),
        "foot_landmarks_available": foot_available,
        "missing_frame_percentage": round(missing_pct, 3),
        "interpolation_percentage": round(interp_pct, 3),
        "jitter_stability_score": round(stability, 4),
        "event_consistency_score": round(event_consistency, 4),
        "gait_metric_completeness": round(metric_completeness, 4),
        "inference_time_sec": round(float(inference_time_sec), 3),
        "keypoint_count": int(seq.all_keypoints().shape[1]),
    }


def compare_backend_results(
    results: dict[str, tuple[PoseSequence, float]],
    failures: dict[str, str] | None = None,
) -> dict[str, Any]:
    scores = {
        name: score_pose_sequence(seq, backend=name, inference_time_sec=elapsed)
        for name, (seq, elapsed) in results.items()
    }
    viable = [
        (name, score)
        for name, score in scores.items()
        if score["valid_pose_percentage"] > 0 and score["average_confidence"] > 0
    ]
    if not viable:
        raise RuntimeError("All available real pose backends failed to return valid keypoints.")
    selected, best = max(viable, key=lambda item: item[1]["final_score"])
    reason = (
        f"Selected {selected}: highest measured gait-quality score "
        f"({best['final_score']:.1f}/100), with {best['valid_pose_percentage']:.1f}% "
        f"valid pose frames and {best['average_confidence']:.3f} mean confidence."
    )
    return {
        "selected_backend": selected,
        "selection_reason": reason,
        "backend_scores": scores,
        "backend_failures": failures or {},
    }
