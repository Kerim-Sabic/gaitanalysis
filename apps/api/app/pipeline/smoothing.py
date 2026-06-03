"""Temporal smoothing of keypoint trajectories.

Pipeline:
  1. Reject low-confidence samples (set to NaN).
  2. Linearly interpolate short gaps; leave long gaps as NaN (reported as missing).
  3. Apply a One Euro filter per coordinate — low lag, adaptive to speed, which
     is the de-facto standard for real-time pose smoothing (Casiez et al. 2012).
"""
from __future__ import annotations

import numpy as np

from app.pipeline.pose.base import PoseSequence


class OneEuroFilter:
    """Scalar One Euro filter operating over a fixed-rate signal."""

    def __init__(self, freq: float, min_cutoff: float = 1.0, beta: float = 0.3,
                 d_cutoff: float = 1.0):
        self.freq = max(freq, 1e-3)
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x_prev: float | None = None
        self._dx_prev: float = 0.0

    @staticmethod
    def _alpha(cutoff: float, freq: float) -> float:
        tau = 1.0 / (2 * np.pi * cutoff)
        te = 1.0 / freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float) -> float:
        if self._x_prev is None or not np.isfinite(self._x_prev):
            self._x_prev = x
            return x
        dx = (x - self._x_prev) * self.freq
        a_d = self._alpha(self.d_cutoff, self.freq)
        dx_hat = a_d * dx + (1 - a_d) * self._dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, self.freq)
        x_hat = a * x + (1 - a) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        return x_hat


class TemporalSmoothingService:
    def __init__(self, min_confidence: float = 0.25, max_gap_frames: int = 8,
                 min_cutoff: float = 1.2, beta: float = 0.25):
        self.min_confidence = min_confidence
        self.max_gap_frames = max_gap_frames
        self.min_cutoff = min_cutoff
        self.beta = beta

    def smooth(self, seq: PoseSequence) -> PoseSequence:
        out = seq.copy()
        kp = out.keypoints
        T, K, _ = kp.shape
        for k in range(K):
            x = kp[:, k, 0].copy()
            y = kp[:, k, 1].copy()
            c = kp[:, k, 2].copy()

            mask = c >= self.min_confidence
            x[~mask] = np.nan
            y[~mask] = np.nan

            x = self._interp_short_gaps(x)
            y = self._interp_short_gaps(y)

            fx = OneEuroFilter(seq.fps, self.min_cutoff, self.beta)
            fy = OneEuroFilter(seq.fps, self.min_cutoff, self.beta)
            for i in range(T):
                if np.isfinite(x[i]):
                    x[i] = fx.filter(x[i])
                if np.isfinite(y[i]):
                    y[i] = fy.filter(y[i])

            kp[:, k, 0] = x
            kp[:, k, 1] = y
        return out

    def _interp_short_gaps(self, arr: np.ndarray) -> np.ndarray:
        a = arr.copy()
        n = len(a)
        isnan = ~np.isfinite(a)
        if not isnan.any():
            return a
        valid_idx = np.where(~isnan)[0]
        if valid_idx.size < 2:
            return a
        i = 0
        while i < n:
            if isnan[i]:
                start = i
                while i < n and isnan[i]:
                    i += 1
                end = i  # first valid after gap
                gap_len = end - start
                if gap_len <= self.max_gap_frames and start > 0 and end < n:
                    a[start:end] = np.linspace(a[start - 1], a[end], gap_len + 2)[1:-1]
                # else leave as NaN (long dropout -> reported missing)
            else:
                i += 1
        return a
