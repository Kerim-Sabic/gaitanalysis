"""Video quality assessment (real signal processing).

Two complementary passes:
  * Frame-based: brightness, blur (variance of Laplacian), resolution, stability
    (inter-frame global motion), and frame-rate/duration adequacy.
  * Pose-based (refinement): full-body & feet visibility and camera-view
    estimation from confident keypoints.

Scores are 0..100 and combined into an overall quality score that gates whether
results should be trusted and feeds the confidence penalty.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.pose.base import KEYPOINT, PoseSequence
from app.pipeline.video_processor import DecodedVideo
from app.schemas import CameraView, QualityResult


def _clip(v: float) -> float:
    return float(max(0.0, min(100.0, v)))


class QualityAssessmentService:
    def __init__(self, min_fps: float = 12.0, min_seconds: float = 2.0):
        self.min_fps = min_fps
        self.min_seconds = min_seconds

    def assess(self, video: DecodedVideo, seq: PoseSequence | None = None) -> QualityResult:
        frames = video.frames
        n = frames.shape[0]
        sample_idx = np.linspace(0, n - 1, min(n, 24)).astype(int)

        brightness_vals, blur_vals = [], []
        prev_gray = None
        motion_vals = []
        for i in sample_idx:
            gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            brightness_vals.append(float(gray.mean()))
            blur_vals.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            if prev_gray is not None and prev_gray.shape == gray.shape:
                diff = cv2.absdiff(gray, prev_gray)
                motion_vals.append(float(diff.mean()))
            prev_gray = gray

        # Detect a synthetic/blank canvas (demo mode with no real footage): frame
        # appearance metrics are meaningless there, so we anchor lighting/blur/
        # stability to the pose-confidence signal instead.
        synthetic = float(np.max(brightness_vals)) < 3.0

        if synthetic:
            conf = float(np.nanmean(seq.keypoints[..., 2])) if seq is not None else 0.6
            lighting = _clip(60 + 35 * conf)
            blur_score = _clip(55 + 40 * conf)
            stability = _clip(70 + 25 * conf)
        else:
            # --- Lighting: penalise very dark / blown-out frames. ---
            mean_b = float(np.mean(brightness_vals))
            lighting = _clip(100.0 - abs(mean_b - 120.0) / 120.0 * 100.0)
            # --- Blur: Laplacian variance; ~100+ is sharp for normalized frames. ---
            sharp = float(np.median(blur_vals))
            blur_score = _clip(np.interp(sharp, [10, 60, 150, 400], [10, 55, 85, 100]))
            # --- Camera stability: motion *consistency* (a moving subject also
            #     creates motion, so we use variability of inter-frame motion). ---
            if motion_vals:
                stability = _clip(
                    100.0 - np.std(motion_vals) / (np.mean(motion_vals) + 1e-6) * 35.0
                )
            else:
                stability = 60.0

        # --- Resolution (always meaningful). ---
        long_edge = max(video.width, video.height)
        resolution = _clip(np.interp(long_edge, [240, 480, 720, 1080], [20, 60, 85, 100]))

        framerate_ok = video.fps >= self.min_fps
        duration_ok = video.duration_sec >= self.min_seconds

        # --- Pose-based refinement. ---
        full_body, feet_vis, view = self._pose_quality(seq)
        pose_details = self._pose_details(seq)

        warnings: list[str] = []
        recs: list[str] = []
        if lighting < 55:
            warnings.append("Lighting is low or uneven.")
            recs.append("Record in even, well-lit conditions; avoid backlight.")
        if blur_score < 55:
            warnings.append("Frames appear blurred or low-detail.")
            recs.append("Hold the camera steady and ensure the subject is in focus.")
        if resolution < 60:
            warnings.append("Low video resolution.")
            recs.append("Record at 720p or higher.")
        if stability < 55:
            warnings.append("Camera movement detected.")
            recs.append("Mount the phone on a tripod or brace it against a fixed surface.")
        if not framerate_ok:
            warnings.append(f"Frame rate ({video.fps:.0f} fps) is low for event timing.")
            recs.append("Record at 30 fps or higher; 60 fps improves event accuracy.")
        if not duration_ok:
            warnings.append("Clip is short; few gait cycles captured.")
            recs.append("Capture several full strides (≥ 5–6 s of steady walking).")
        if full_body < 60:
            warnings.append("Full body not consistently visible.")
            recs.append("Frame the whole body head-to-feet for the entire walk.")
        if feet_vis < 55:
            warnings.append("Feet/ankles poorly visible — event timing is limited.")
            recs.append("Keep feet in frame and unobstructed; avoid long grass / shadows.")

        overall = _clip(
            0.16 * lighting + 0.16 * blur_score + 0.12 * resolution + 0.14 * stability
            + 0.22 * full_body + 0.20 * feet_vis
            - (0 if framerate_ok else 10) - (0 if duration_ok else 8)
        )
        if pose_details["pose_valid_percentage"] <= 0:
            status = "FAIL_NO_PERSON"
        elif not duration_ok:
            status = "FAIL_VIDEO_TOO_SHORT"
        elif pose_details["feet_visibility_confidence"] < 0.15:
            status = "FAIL_FEET_NOT_VISIBLE"
        elif pose_details["average_confidence"] < 0.20:
            status = "FAIL_LOW_CONFIDENCE"
        elif (
            pose_details["pose_valid_percentage"] >= 60
            and pose_details["feet_visibility_confidence"] >= 0.45
            and overall >= 70
        ):
            status = "PASS"
        else:
            status = "PASS_WITH_LIMITATIONS"
        if pose_details["pose_valid_percentage"] < 60:
            warnings.append(
                f"Pose was confidently valid in only "
                f"{pose_details['pose_valid_percentage']:.0f}% of frames."
            )

        return QualityResult(
            overall_score=round(overall, 1),
            lighting_score=round(lighting, 1),
            blur_score=round(blur_score, 1),
            resolution_score=round(resolution, 1),
            full_body_visibility=round(full_body, 1),
            feet_visibility=round(feet_vis, 1),
            camera_stability=round(stability, 1),
            duration_ok=duration_ok,
            framerate_ok=framerate_ok,
            detected_view=view,
            status=status,
            pose_valid_percentage=round(pose_details["pose_valid_percentage"], 1),
            person_size_percent=round(pose_details["person_size_percent"], 1),
            ankle_confidence=round(pose_details["ankle_confidence"], 3),
            heel_confidence=round(pose_details["heel_confidence"], 3),
            foot_index_confidence=round(pose_details["foot_index_confidence"], 3),
            multi_person_risk=0.0,
            occlusion_missing_percentage=round(pose_details["missing_percentage"], 1),
            warnings=warnings,
            recommendations=recs,
        )

    def _pose_quality(self, seq: PoseSequence | None) -> tuple[float, float, CameraView]:
        if seq is None or seq.num_frames == 0:
            return 50.0, 50.0, CameraView.unknown
        scores = seq.keypoints[..., 2]
        body_idx = [KEYPOINT[n] for n in (
            "left_shoulder", "right_shoulder", "left_hip", "right_hip",
            "left_knee", "right_knee", "left_ankle", "right_ankle",
        )]
        feet_idx = [KEYPOINT["left_ankle"], KEYPOINT["right_ankle"]]
        # "Visible" means *confidently* tracked (>=0.5), a higher bar than the
        # presence threshold used for detection — low-confidence pose lowers this.
        full_body = float((scores[:, body_idx] > 0.5).mean()) * 100.0
        feet_vis = float((scores[:, feet_idx] > 0.5).mean()) * 100.0

        # View estimation: shoulder/hip horizontal spread relative to body height.
        kp = seq.keypoints
        sh = np.abs(kp[:, KEYPOINT["left_shoulder"], 0] - kp[:, KEYPOINT["right_shoulder"], 0])
        body_h = np.abs(kp[:, KEYPOINT["left_ankle"], 1] - kp[:, KEYPOINT["left_shoulder"], 1])
        ratio = float(np.nanmedian(sh / (body_h + 1e-6)))
        view = CameraView.coronal if ratio > 0.22 else CameraView.sagittal
        return _clip(full_body), _clip(feet_vis), view

    @staticmethod
    def _pose_details(seq: PoseSequence | None) -> dict[str, float]:
        empty = {
            "pose_valid_percentage": 0.0,
            "person_size_percent": 0.0,
            "average_confidence": 0.0,
            "ankle_confidence": 0.0,
            "heel_confidence": 0.0,
            "foot_index_confidence": 0.0,
            "feet_visibility_confidence": 0.0,
            "missing_percentage": 100.0,
        }
        if seq is None or seq.num_frames == 0:
            return empty
        names = seq.all_names()
        all_kp = seq.all_keypoints()
        scores = all_kp[..., 2]
        frame_mean = np.nanmean(scores, axis=1)

        def conf(wanted):
            idx = [names.index(name) for name in wanted if name in names]
            return float(np.nanmean(scores[:, idx])) if idx else 0.0

        areas = []
        for frame in all_kp:
            visible = frame[:, 2] >= 0.25
            if visible.sum() >= 4:
                xs, ys = frame[visible, 0], frame[visible, 1]
                areas.append(
                    max(0.0, float(xs.max() - xs.min()))
                    * max(0.0, float(ys.max() - ys.min()))
                    / max(float(seq.width * seq.height), 1.0)
                    * 100.0
                )
        ankle = conf(["left_ankle", "right_ankle"])
        heel = conf(["left_heel", "right_heel"])
        foot = conf(["left_foot_index", "right_foot_index"])
        return {
            "pose_valid_percentage": float(np.mean(frame_mean > 0.30) * 100.0),
            "person_size_percent": float(np.median(areas)) if areas else 0.0,
            "average_confidence": float(np.nanmean(scores)) if scores.size else 0.0,
            "ankle_confidence": ankle,
            "heel_confidence": heel,
            "foot_index_confidence": foot,
            "feet_visibility_confidence": float(np.mean([v for v in (ankle, heel, foot) if v > 0]))
            if any(v > 0 for v in (ankle, heel, foot)) else 0.0,
            "missing_percentage": float(np.mean(scores < 0.20) * 100.0),
        }
