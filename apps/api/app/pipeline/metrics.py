"""Gait metric computation from smoothed keypoints + detected events.

Everything here is computed from the data — no hard-coded results. Where a value
needs spatial calibration (e.g. walking speed in m/s) we either use a provided
calibration distance, estimate pixels-per-metre from a known subject height, or
fall back to a clearly-labelled normalised estimate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.pipeline.events import EventSet
from app.pipeline.pose.base import KEYPOINT, PoseSequence
from app.pipeline.reference import (
    asymmetry_status,
    in_range_status,
    reference_text,
)
from app.schemas import (
    Asymmetry,
    JointCurve,
    JointCurvePoint,
    Metric,
    MetricStatus,
    QualityResult,
)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Interior angle (deg) at b for the joint a-b-c, per frame. Shapes (T,2)."""
    ba = a - b
    bc = c - b
    nba = np.linalg.norm(ba, axis=1) + 1e-9
    nbc = np.linalg.norm(bc, axis=1) + 1e-9
    cos = np.einsum("ij,ij->i", ba, bc) / (nba * nbc)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def _cv(values: list[float]) -> float | None:
    arr = np.asarray([v for v in values if np.isfinite(v)])
    if arr.size < 2 or arr.mean() == 0:
        return None
    return float(arr.std() / arr.mean())


@dataclass
class MetricsBundle:
    metrics: list[Metric] = field(default_factory=list)
    asymmetry: list[Asymmetry] = field(default_factory=list)
    joint_curves: list[JointCurve] = field(default_factory=list)
    risk_score: float = 0.0
    risk_band: str = "review"
    overall_confidence: float = 0.0
    stride_cv: float | None = None
    calibration_status: str = "uncalibrated"
    limitations: list[str] = field(default_factory=list)


class GaitMetricsCalculator:
    def __init__(self):
        pass

    def compute(
        self,
        seq: PoseSequence,
        events: EventSet,
        quality: QualityResult,
        *,
        height_cm: float | None = None,
        calibration_distance_m: float | None = None,
    ) -> MetricsBundle:
        b = MetricsBundle()
        kp = seq.keypoints
        fps = seq.fps

        # --- Pixels-per-metre calibration. ---
        px_per_m, calib_status, calib_conf = self._calibrate(seq, height_cm, calibration_distance_m)
        b.calibration_status = calib_status

        # --- Temporal metrics from events. ---
        hs_all = sorted(
            [(t, s) for s in ("left", "right") for t in events.heel_strikes.get(s, [])]
        )
        n_steps = len(hs_all)
        walking_time = (hs_all[-1][0] - hs_all[0][0]) if n_steps >= 2 else 0.0

        step_times = [hs_all[i + 1][0] - hs_all[i][0] for i in range(len(hs_all) - 1)]
        cadence = (60.0 / np.mean(step_times)) if step_times else None

        side_step_time, side_stride_time, side_stance, side_swing = {}, {}, {}, {}
        for side in ("left", "right"):
            hs = sorted(events.heel_strikes.get(side, []))
            to = sorted(events.toe_offs.get(side, []))
            strides = [hs[i + 1] - hs[i] for i in range(len(hs) - 1)]
            side_stride_time[side] = float(np.mean(strides)) if strides else None
            # step ending at this side's heel strike = time since previous opposite HS
            other = "right" if side == "left" else "left"
            other_hs = sorted(events.heel_strikes.get(other, []))
            steps = []
            for h in hs:
                prev = [o for o in other_hs if o < h]
                if prev:
                    steps.append(h - prev[-1])
            side_step_time[side] = float(np.mean(steps)) if steps else None
            # stance = HS -> next TO (same foot); swing = TO -> next HS
            stance, swing = [], []
            for h in hs:
                nto = [o for o in to if o > h]
                if nto:
                    stance.append(nto[0] - h)
            for o in to:
                nhs = [h for h in hs if h > o]
                if nhs:
                    swing.append(nhs[0] - o)
            side_stance[side] = float(np.mean(stance)) if stance else None
            side_swing[side] = float(np.mean(swing)) if swing else None

        all_strides = [
            s for side in ("left", "right")
            for s in [
                events.heel_strikes[side][i + 1] - events.heel_strikes[side][i]
                for i in range(len(events.heel_strikes.get(side, [])) - 1)
            ]
        ]
        b.stride_cv = _cv(all_strides)

        # --- Joint angle curves & ROM. ---
        rom = {}
        for side in ("left", "right"):
            knee = _angle(
                kp[:, KEYPOINT[f"{side}_hip"], :2],
                kp[:, KEYPOINT[f"{side}_knee"], :2],
                kp[:, KEYPOINT[f"{side}_ankle"], :2],
            )
            knee_flex = 180.0 - knee  # 0 = straight leg
            self._add_curve(b, seq, f"knee_{side}", f"Knee flexion ({side})", knee_flex)
            rom[f"knee_{side}"] = self._rom(knee_flex)

            # hip angle: thigh (hip->knee) vs trunk (hip->shoulder)
            hip = _angle(
                kp[:, KEYPOINT[f"{side}_shoulder"], :2],
                kp[:, KEYPOINT[f"{side}_hip"], :2],
                kp[:, KEYPOINT[f"{side}_knee"], :2],
            )
            hip_excursion = 180.0 - hip
            self._add_curve(b, seq, f"hip_{side}", f"Hip excursion ({side})", hip_excursion)
            rom[f"hip_{side}"] = self._rom(hip_excursion)

        # trunk sway: trunk vector (pelvis->neck) tilt from vertical, per frame
        pelvis = _nanmean_tracks(
            kp[:, KEYPOINT["left_hip"], :2], kp[:, KEYPOINT["right_hip"], :2]
        )
        neck = _nanmean_tracks(
            kp[:, KEYPOINT["left_shoulder"], :2], kp[:, KEYPOINT["right_shoulder"], :2]
        )
        trunk_vec = neck - pelvis
        trunk_tilt = np.degrees(np.arctan2(trunk_vec[:, 0], -trunk_vec[:, 1]))
        self._add_curve(b, seq, "trunk", "Trunk tilt", trunk_tilt)
        trunk_sway_index = float(np.nanstd(trunk_tilt)) if np.isfinite(trunk_tilt).any() else None

        # --- Spatial metrics (need calibration). ---
        finite = np.isfinite(pelvis[:, 0])
        speed_mps = stride_len_m = None
        if finite.sum() > 2 and walking_time > 0:
            disp_px = abs(np.nanmax(pelvis[finite, 0]) - np.nanmin(pelvis[finite, 0]))
            if calibration_distance_m:
                speed_mps = calibration_distance_m / walking_time
                px_per_m = (disp_px / calibration_distance_m) if disp_px > 0 else px_per_m
            elif px_per_m:
                speed_mps = (disp_px / px_per_m) / walking_time
            mean_stride_t = np.nanmean(
                [v for v in side_stride_time.values() if v]
            ) if any(side_stride_time.values()) else None
            if px_per_m and mean_stride_t and speed_mps:
                stride_len_m = speed_mps * mean_stride_t

        # --- Pack metrics. ---
        kp_conf = float(np.nanmean(kp[..., 2]))
        cycle_factor = min(1.0, len(all_strides) / 4.0)
        base_conf = float(np.clip(0.55 * kp_conf + 0.3 * (quality.overall_score / 100)
                                  + 0.15 * cycle_factor, 0, 1))

        self._metric(b, "cadence_steps_per_min", "Cadence", cadence, "steps/min", base_conf,
                     ref_key="cadence_steps_per_min")
        self._metric(b, "step_count", "Step count", float(n_steps), "steps",
                     min(0.95, base_conf + 0.05))
        self._metric(b, "gait_cycles_detected", "Gait cycles", float(len(all_strides)), "cycles",
                     min(0.95, base_conf + 0.05))

        if speed_mps is not None:
            speed_conf = base_conf * (1.0 if calibration_distance_m else (0.7 if height_cm else 0.5))
            self._metric(b, "walking_speed_m_per_s", "Walking speed", round(speed_mps, 3), "m/s",
                         speed_conf, ref_key="walking_speed_m_per_s",
                         extra="" if calibration_distance_m else
                         "Estimated from video scale; confirm with a calibrated distance.")

        self._metric(b, "left_step_time_sec", "Left step time", _r(side_step_time["left"]), "s",
                     base_conf, ref_key="step_time_sec")
        self._metric(b, "right_step_time_sec", "Right step time", _r(side_step_time["right"]), "s",
                     base_conf, ref_key="step_time_sec")
        self._metric(b, "left_stride_time_sec", "Left stride time", _r(side_stride_time["left"]),
                     "s", base_conf)
        self._metric(b, "right_stride_time_sec", "Right stride time", _r(side_stride_time["right"]),
                     "s", base_conf)

        self._metric(b, "knee_rom_left_deg", "Knee ROM (left)", _r(rom.get("knee_left")), "°",
                     base_conf, ref_key="knee_rom_deg")
        self._metric(b, "knee_rom_right_deg", "Knee ROM (right)", _r(rom.get("knee_right")), "°",
                     base_conf, ref_key="knee_rom_deg")
        self._metric(b, "hip_rom_left_deg", "Hip ROM (left)", _r(rom.get("hip_left")), "°",
                     base_conf, ref_key="hip_rom_deg")
        self._metric(b, "hip_rom_right_deg", "Hip ROM (right)", _r(rom.get("hip_right")), "°",
                     base_conf, ref_key="hip_rom_deg")

        if trunk_sway_index is not None:
            self._metric(b, "trunk_sway_index", "Trunk sway index", round(trunk_sway_index, 2),
                         "° (SD)", base_conf * 0.8,
                         interp="Angular trunk variability; higher values suggest instability.")
        if b.stride_cv is not None:
            self._metric(b, "stride_time_variability", "Stride-time variability",
                         round(b.stride_cv * 100, 1), "% CV", base_conf,
                         interp="Stride-to-stride timing variability.")
        if stride_len_m is not None:
            self._metric(b, "stride_length_m", "Stride length", round(stride_len_m, 2), "m",
                         base_conf * (0.8 if calibration_distance_m else 0.55))

        # --- Asymmetry. ---
        self._asym(b, "step_time_asymmetry", "Step time", side_step_time["left"],
                   side_step_time["right"], "s", base_conf)
        self._asym(b, "stride_time_asymmetry", "Stride time", side_stride_time["left"],
                   side_stride_time["right"], "s", base_conf)
        self._asym(b, "stance_time_asymmetry", "Stance time", side_stance["left"],
                   side_stance["right"], "s", base_conf)
        self._asym(b, "knee_rom_asymmetry", "Knee ROM", rom.get("knee_left"),
                   rom.get("knee_right"), "°", base_conf)

        # --- Mobility Risk Support Score (cautious composite). ---
        b.risk_score, b.risk_band = self._risk_score(
            step_asym=_asym_pct(side_step_time["left"], side_step_time["right"]),
            cadence=cadence, speed=speed_mps, stride_cv=b.stride_cv,
            trunk_sway=trunk_sway_index,
        )
        b.overall_confidence = round(base_conf, 3)

        # --- Limitations. ---
        if calib_status == "uncalibrated":
            b.limitations.append(
                "No spatial calibration: distance/speed metrics are approximate or omitted."
            )
        b.limitations.append(
            "Single-camera 2D analysis limits depth and out-of-plane motion accuracy."
        )
        if not all(
            name in seq.all_names()
            for name in ("left_heel", "right_heel", "left_foot_index", "right_foot_index")
        ):
            b.limitations.append(
                "Dedicated heel/foot-index landmarks were unavailable; event timing uses "
                "an ankle-based fallback with reduced confidence."
            )
        if len(all_strides) < 4:
            b.limitations.append("Few gait cycles captured; variability estimates are limited.")
        return b

    # ------------------------------------------------------------------ #
    def _calibrate(self, seq, height_cm, calib_dist):
        if calib_dist:
            return None, "distance-calibrated", 0.9
        if height_cm:
            kp = seq.keypoints
            head_y = kp[:, KEYPOINT["nose"], 1]
            ankle_y = np.nanmean(
                [kp[:, KEYPOINT["left_ankle"], 1], kp[:, KEYPOINT["right_ankle"], 1]], axis=0
            )
            body_px = np.nanmedian(np.abs(ankle_y - head_y))
            if np.isfinite(body_px) and body_px > 1:
                # nose-to-ankle ~ 0.875 of stature
                px_per_m = body_px / (0.875 * (height_cm / 100.0))
                return float(px_per_m), "height-calibrated", 0.65
        return None, "uncalibrated", 0.4

    def _add_curve(self, b, seq, key, label, values):
        t = seq.timestamps
        finite = np.isfinite(values)
        if finite.sum() < 2:
            return
        idx = np.linspace(0, len(values) - 1, min(len(values), 160)).astype(int)
        samples = [
            JointCurvePoint(t=round(float(t[i]), 3), value=round(float(values[i]), 2))
            for i in idx if np.isfinite(values[i])
        ]
        vals = values[finite]
        b.joint_curves.append(JointCurve(
            key=key, label=label, unit="deg",
            min=round(float(vals.min()), 2), max=round(float(vals.max()), 2),
            rom=round(float(vals.max() - vals.min()), 2), samples=samples,
        ))

    @staticmethod
    def _rom(values):
        f = values[np.isfinite(values)]
        if f.size < 2:
            return None
        # robust ROM: 95th - 5th percentile to reject spikes
        return float(np.percentile(f, 95) - np.percentile(f, 5))

    def _metric(self, b, key, label, value, unit, conf, *, ref_key=None, interp="", extra=""):
        status, text = (MetricStatus.limited, "")
        if ref_key and value is not None:
            status, text = in_range_status(value, ref_key)
        if value is None:
            status = MetricStatus.limited
            text = "Could not be computed from this video."
        elif conf < 0.45:
            status = MetricStatus.low_confidence
        interpretation = " ".join(x for x in [interp or text, extra] if x).strip()
        b.metrics.append(Metric(
            key=key, label=label, value=value, unit=unit, confidence=round(conf, 3),
            status=status, normal_reference=reference_text(ref_key) if ref_key else None,
            interpretation=interpretation,
        ))

    def _asym(self, b, key, label, left, right, unit, conf):
        pct = _asym_pct(left, right)
        status, text = asymmetry_status(pct)
        b.asymmetry.append(Asymmetry(
            key=key, label=label, left=_r(left), right=_r(right),
            asymmetry_percent=_r(pct), unit=unit, confidence=round(conf, 3),
            status=status, interpretation=text,
        ))

    @staticmethod
    def _risk_score(step_asym, cadence, speed, stride_cv, trunk_sway):
        """Cautious 0–100 composite. Higher = more aspects warranting review."""
        parts, weights = [], []

        def add(val, weight):
            if val is not None:
                parts.append(float(np.clip(val, 0, 1)))
                weights.append(weight)

        if step_asym is not None:
            add(step_asym / 25.0, 0.30)  # 25% asym -> full
        if cadence is not None:
            add(max(0.0, (95.0 - cadence) / 55.0), 0.20)  # slow cadence
        if speed is not None:
            add(max(0.0, (1.0 - speed) / 0.6), 0.20)  # <1.0 m/s ramps up
        if stride_cv is not None:
            add((stride_cv - 0.03) / 0.10, 0.15)  # CV above ~3%
        if trunk_sway is not None:
            add((trunk_sway - 2.0) / 8.0, 0.15)  # sway SD above ~2°

        if not parts:
            return 0.0, "insufficient_data"
        score = float(np.average(parts, weights=weights) * 100.0)
        score = round(min(100.0, score), 1)
        band = "low" if score < 25 else ("review" if score < 50 else "elevated_review")
        return score, band


def _r(v, ndigits: int = 3):
    return None if v is None or not np.isfinite(v) else round(float(v), ndigits)


def _asym_pct(left, right):
    if left is None or right is None:
        return None
    mean = (abs(left) + abs(right)) / 2.0
    if mean == 0:
        return None
    return abs(left - right) / mean * 100.0


def _nanmean_tracks(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    stack = np.stack([left, right], axis=0)
    count = np.sum(np.isfinite(stack), axis=0)
    return np.divide(
        np.nansum(stack, axis=0),
        count,
        out=np.full_like(left, np.nan, dtype=float),
        where=count > 0,
    )
