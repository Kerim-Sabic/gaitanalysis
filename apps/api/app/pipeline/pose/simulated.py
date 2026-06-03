"""Simulated / fallback pose estimator.

This is the honest fallback used when no real pose model is installed (or when a
demo preset is explicitly requested). It synthesises a physiologically-plausible
**sagittal-plane** walking skeleton using forward kinematics over a gait cycle.

CRITICAL HONESTY NOTE
---------------------
The keypoints are *simulated*. However, the downstream gait pipeline (event
detection, metrics, asymmetry, flags) is the REAL pipeline and measures whatever
keypoints it is given. So demo metrics are genuinely *computed* from the
synthetic motion — they are not hand-typed constants. Output is always labelled
``analysis_mode = demo`` / "Not clinical-grade".

The ``asymmetry`` parameter drives two independent, measurable channels:
  * a temporal channel (left foot phase offset != exactly half a cycle ->
    unequal left/right step times), and
  * a spatial channel (per-side scaling of hip swing & knee flexion -> ROM
    asymmetry).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import COCO17_NAMES, KEYPOINT, BasePoseEstimator, PoseModelInfo, PoseSequence


@dataclass
class GaitProfile:
    cadence_spm: float = 110.0          # steps per minute
    asymmetry: float = 0.03             # drives temporal + spatial asymmetry
    knee_flex_deg: float = 60.0         # peak knee flexion in swing
    hip_swing_deg: float = 27.0         # thigh excursion about vertical
    trunk_lean_deg: float = 4.0         # mean forward trunk lean
    speed_factor: float = 1.0           # progression speed multiplier
    body_scale: float = 0.40            # subject height as fraction of frame
    noise_px: float = 1.4               # gaussian keypoint jitter
    base_confidence: float = 0.93       # mean keypoint score
    variability: float = 0.02           # stride-to-stride timing modulation
    degrade: bool = False               # render a poor capture (dark/blur/noise)
    width: int = 1280                   # demo render width
    height: int = 720                   # demo render height


PRESETS: dict[str, GaitProfile] = {
    "normal": GaitProfile(asymmetry=0.0),
    "asymmetric": GaitProfile(
        cadence_spm=98.0, asymmetry=0.09, knee_flex_deg=52.0,
        hip_swing_deg=22.0, trunk_lean_deg=7.0, variability=0.05,
    ),
    "poor_quality": GaitProfile(
        cadence_spm=106.0, asymmetry=0.06, noise_px=5.0, base_confidence=0.45,
        variability=0.07, degrade=True, width=640, height=360,
    ),
    "tug": GaitProfile(
        cadence_spm=86.0, asymmetry=0.06, knee_flex_deg=50.0,
        speed_factor=0.78, trunk_lean_deg=8.0, variability=0.06,
    ),
}


class SimulatedPoseEstimator(BasePoseEstimator):
    """Lightweight, dependency-free fallback estimator."""

    def __init__(self, profile: GaitProfile | None = None, seed: int = 7):
        self.profile = profile or GaitProfile()
        self.rng = np.random.default_rng(seed)

    @classmethod
    def from_preset(cls, preset: str, seed: int = 7) -> "SimulatedPoseEstimator":
        return cls(PRESETS.get(preset, PRESETS["normal"]), seed=seed)

    def get_model_info(self) -> PoseModelInfo:
        return PoseModelInfo(
            name="HoralixSimKinematic",
            version="0.1.0",
            keypoint_format="COCO-17",
            is_clinical_grade=False,
            notes=[
                "Simulated sagittal-plane kinematics — NOT clinical-grade.",
                "Metrics are computed by the real pipeline from synthetic motion.",
            ],
        )

    # ------------------------------------------------------------------ #
    def estimate_2d_pose(self, frames: np.ndarray, fps: float) -> PoseSequence:
        n = int(frames.shape[0]) if frames is not None and frames.ndim == 4 else 0
        h = int(frames.shape[1]) if n else 720
        w = int(frames.shape[2]) if n else 1280
        if n == 0:
            n = int(fps * 7)
        return self._synthesize(n, fps, w, h)

    # ------------------------------------------------------------------ #
    def _synthesize(self, n: int, fps: float, w: int, h: int) -> PoseSequence:
        p = self.profile
        t = np.arange(n) / fps

        step_freq = p.cadence_spm / 60.0          # steps / s
        stride_freq = step_freq / 2.0
        # Base stride phase with mild frequency modulation -> stride-time variability.
        fmod = p.variability * np.sin(2 * np.pi * 0.27 * t)
        phase = 2 * np.pi * stride_freq * t + fmod

        body_h = p.body_scale * h
        thigh = 0.245 * body_h
        shank = 0.246 * body_h
        torso = 0.30 * body_h
        head = 0.13 * body_h

        x_start, x_end = 0.06 * w, 0.94 * w
        prog = (t / t[-1]) if t[-1] > 0 else np.zeros_like(t)
        prog = np.clip(prog * p.speed_factor, 0, 1)
        pelvis_x = x_start + (x_end - x_start) * prog
        pelvis_y = (0.50 * h) + 0.012 * body_h * np.cos(2 * phase)

        kp = np.zeros((n, 17, 3), dtype=np.float64)

        def fk_leg(phase_offset: float, hip_scale: float, knee_scale: float):
            ph = phase + phase_offset
            thigh_ang = np.deg2rad(p.hip_swing_deg * hip_scale) * np.sin(ph)
            swing_gate = np.clip(np.sin(ph - np.pi / 2), 0, 1) ** 1.4
            knee_ang = np.deg2rad(p.knee_flex_deg * knee_scale) * swing_gate
            hip_x, hip_y = pelvis_x, pelvis_y
            knee_x = hip_x + thigh * np.sin(thigh_ang)
            knee_y = hip_y + thigh * np.cos(thigh_ang)
            shank_ang = thigh_ang - knee_ang
            ank_x = knee_x + shank * np.sin(shank_ang)
            ank_y = knee_y + shank * np.cos(shank_ang)
            return (hip_x, hip_y), (knee_x, knee_y), (ank_x, ank_y)

        a = p.asymmetry
        # Right leg = reference; left leg phase-shifted by slightly more/less than
        # half a cycle (temporal asymmetry) and scaled down (spatial asymmetry).
        (rh, rk, ra) = fk_leg(0.0, 1.0 + a / 2, 1.0 + a / 2)
        (lh, lk, la) = fk_leg(np.pi * (1.0 + a), 1.0 - a / 2, 1.0 - a / 2)

        trunk_lean = np.deg2rad(p.trunk_lean_deg)
        neck_x = pelvis_x + torso * np.sin(trunk_lean)
        neck_y = pelvis_y - torso * np.cos(trunk_lean)
        sh_half = 0.11 * body_h
        hip_half = 0.08 * body_h
        arm = 0.16 * body_h

        def setp(idx, x, y):
            kp[:, idx, 0] = x
            kp[:, idx, 1] = y

        setp(KEYPOINT["nose"], neck_x + 0.1 * head * np.sin(trunk_lean), neck_y - head)
        setp(KEYPOINT["left_eye"], neck_x - 0.03 * head, neck_y - head - 0.05 * head)
        setp(KEYPOINT["right_eye"], neck_x + 0.03 * head, neck_y - head - 0.05 * head)
        setp(KEYPOINT["left_ear"], neck_x - 0.06 * head, neck_y - head)
        setp(KEYPOINT["right_ear"], neck_x + 0.06 * head, neck_y - head)
        setp(KEYPOINT["left_shoulder"], neck_x - sh_half * 0.4, neck_y)
        setp(KEYPOINT["right_shoulder"], neck_x + sh_half * 0.4, neck_y)
        setp(KEYPOINT["left_elbow"], neck_x - arm * np.sin(phase) * 0.5, neck_y + 0.45 * arm)
        setp(KEYPOINT["right_elbow"], neck_x + arm * np.sin(phase) * 0.5, neck_y + 0.45 * arm)
        setp(KEYPOINT["left_wrist"], neck_x - arm * np.sin(phase), neck_y + 0.9 * arm)
        setp(KEYPOINT["right_wrist"], neck_x + arm * np.sin(phase), neck_y + 0.9 * arm)
        setp(KEYPOINT["left_hip"], lh[0] - hip_half * 0.3, lh[1])
        setp(KEYPOINT["right_hip"], rh[0] + hip_half * 0.3, rh[1])
        setp(KEYPOINT["left_knee"], lk[0], lk[1])
        setp(KEYPOINT["right_knee"], rk[0], rk[1])
        setp(KEYPOINT["left_ankle"], la[0], la[1])
        setp(KEYPOINT["right_ankle"], ra[0], ra[1])

        kp[..., 2] = np.clip(
            p.base_confidence + self.rng.normal(0, 0.04, size=(n, 17)), 0.05, 0.99
        )
        kp[..., :2] += self.rng.normal(0, p.noise_px, size=(n, 17, 2))

        return PoseSequence(
            keypoints=kp, fps=fps, width=w, height=h, timestamps=t, names=list(COCO17_NAMES)
        )
