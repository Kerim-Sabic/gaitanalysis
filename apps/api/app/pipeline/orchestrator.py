"""Pipeline orchestrator — wires the modular stages into one analysis run.

    video -> quality -> detection -> pose -> smoothing -> events ->
    metrics -> clinical flags -> narrative/report

Emits progress via a callback so the API can stream stage updates to the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from app.config import get_settings
from app.pipeline.events import GaitEventDetector
from app.pipeline.flags import ClinicalFlagService
from app.pipeline.metrics import GaitMetricsCalculator
from app.pipeline.narrative import NarrativeGenerator
from app.pipeline.pose import select_pose_estimator
from app.pipeline.pose.base import LEFT_INDICES, RIGHT_INDICES, SKELETON_EDGES
from app.pipeline.quality import QualityAssessmentService
from app.pipeline.smoothing import TemporalSmoothingService
from app.pipeline.tracking import PersonDetectionService
from app.pipeline.video_processor import VideoError, VideoProcessor
from app.schemas import (
    AnalysisMode,
    AnalysisStatus,
    GaitAnalysisResult,
    ModelInfo,
    PatientCase,
    PoseFrame,
    PoseTrack,
    TestType,
    VideoMetadata,
)

PIPELINE_VERSION = "0.1.0"

STAGES = [
    ("decode", "Video decoded"),
    ("detect", "Person detected"),
    ("pose", "Pose estimated"),
    ("smooth", "Motion smoothed"),
    ("events", "Gait events detected"),
    ("metrics", "Metrics calculated"),
    ("report", "Report generated"),
]

ProgressCb = Callable[[str, float], None]


class AnalysisError(Exception):
    def __init__(self, message: str, code: str = "analysis_failed"):
        super().__init__(message)
        self.code = code


@dataclass
class AnalysisOutput:
    result: GaitAnalysisResult
    pose_track: PoseTrack


class GaitPipeline:
    def __init__(self):
        self.video_proc = VideoProcessor()
        self.quality_svc = QualityAssessmentService()
        self.detect_svc = PersonDetectionService()
        self.smooth_svc = TemporalSmoothingService()
        self.event_detector = GaitEventDetector()
        self.metrics_calc = GaitMetricsCalculator()
        self.flag_svc = ClinicalFlagService()
        self.narrator = NarrativeGenerator()

    def run(
        self,
        *,
        analysis_id: str,
        case: PatientCase,
        video: VideoMetadata,
        test_type: TestType,
        demo_preset: Optional[str] = None,
        progress: Optional[ProgressCb] = None,
    ) -> AnalysisOutput:
        settings = get_settings()

        def emit(stage: str, frac: float):
            if progress:
                progress(stage, frac)

        # 1) Decode (or synthesize a frame canvas for pure-demo runs).
        is_demo_canvas = bool(demo_preset and not _video_exists(video.stored_path))
        try:
            if is_demo_canvas:
                from app.pipeline.pose.simulated import PRESETS

                prof = PRESETS.get(demo_preset, PRESETS["normal"])
                decoded = _DemoCanvas(test_type, width=prof.width, height=prof.height)
            else:
                decoded = self.video_proc.load(
                    video.stored_path, min_seconds=settings.min_video_seconds
                )
        except VideoError as e:
            raise AnalysisError(str(e), code="video_invalid") from e
        emit("decode", 1 / len(STAGES))

        # 2) Pose estimation (select backend; may fall back to simulated/demo).
        estimator, mode = select_pose_estimator(settings.pose_backend, demo_preset)
        seq = estimator.estimate_2d_pose(decoded.frames, decoded.fps)
        if seq.num_frames == 0:
            raise AnalysisError("No frames available for pose estimation.", "no_person")

        # 2a) For demo runs, render the simulated subject into REAL frames so
        #     quality scoring is genuine and a playable clip can be produced.
        from app.pipeline.pose.simulated import SimulatedPoseEstimator

        if is_demo_canvas and isinstance(estimator, SimulatedPoseEstimator):
            from app.pipeline.demo_scene import render_scene, write_mp4

            decoded.frames = render_scene(seq, estimator.profile)
            decoded.height, decoded.width = decoded.frames.shape[1], decoded.frames.shape[2]
            clip_path = settings.uploads_dir / f"{video.id}_demo.mp4"
            if write_mp4(decoded.frames, decoded.fps, clip_path):
                video.stored_path = str(clip_path)  # persisted by the caller

        # 2b) Person detection / dominant-subject + multi-person guard.
        track = self.detect_svc.analyze(seq)
        if track.num_candidates == 0 or track.coverage < 0.2:
            raise AnalysisError(
                "No person was reliably detected for enough of the clip.", "no_person"
            )
        if track.multiple_people:
            raise AnalysisError(
                "Multiple people detected; isolate a single subject and retry.",
                "multiple_people",
            )
        emit("detect", 2 / len(STAGES))
        emit("pose", 3 / len(STAGES))

        # 3) Temporal smoothing.
        smoothed = self.smooth_svc.smooth(seq)
        emit("smooth", 4 / len(STAGES))

        # 4) Quality (uses raw frames + pose coverage).
        quality = self.quality_svc.assess(decoded, smoothed)

        # 5) Gait events.
        events = self.event_detector.detect(smoothed)
        emit("events", 5 / len(STAGES))

        # 6) Metrics.
        bundle = self.metrics_calc.compute(
            smoothed, events, quality,
            height_cm=case.height_cm,
            calibration_distance_m=video.calibration_distance_m,
        )
        emit("metrics", 6 / len(STAGES))

        # 7) Flags + narrative.
        flags = self.flag_svc.generate(bundle, quality)
        narrative = self.narrator.generate(bundle, quality, flags, test_type, mode)

        info = estimator.get_model_info()
        model_info = ModelInfo(
            pose_model=info.name,
            pose_model_version=info.version,
            analysis_mode=mode,
            keypoint_format=info.keypoint_format,
            pipeline_version=PIPELINE_VERSION,
            frame_count=smoothed.num_frames,
            fps=round(smoothed.fps, 2),
            mean_keypoint_confidence=round(smoothed.mean_confidence, 3),
            calibration_status=bundle.calibration_status,
            notes=info.notes,
        )

        result = GaitAnalysisResult(
            analysis_id=analysis_id,
            case_id=case.id,
            video_id=video.id,
            status=AnalysisStatus.completed,
            test_type=test_type,
            analysis_mode=mode,
            quality=quality,
            metrics=bundle.metrics,
            asymmetry=bundle.asymmetry,
            events=events.events,
            joint_curves=bundle.joint_curves,
            clinical_flags=flags,
            mobility_risk_support_score=bundle.risk_score,
            mobility_risk_band=bundle.risk_band,
            overall_confidence=bundle.overall_confidence,
            limitations=bundle.limitations + (events.notes or []),
            report_summary=narrative["report_summary"],
            patient_summary=narrative["patient_summary"],
            recommendations=narrative["recommendations"],
            model_info=model_info,
        )
        pose_track = self._build_pose_track(analysis_id, smoothed)
        emit("report", 7 / len(STAGES))
        return AnalysisOutput(result=result, pose_track=pose_track)

    @staticmethod
    def _build_pose_track(analysis_id: str, seq) -> PoseTrack:
        frames: list[PoseFrame] = []
        kp = seq.keypoints
        for i in range(seq.num_frames):
            pts = [[round(float(x), 1), round(float(y), 1), round(float(s), 3)]
                   for x, y, s in kp[i]]
            mc = float(np.nanmean(kp[i, :, 2]))
            frames.append(PoseFrame(
                frame_index=i, t=round(float(seq.timestamps[i]), 3),
                keypoints=pts, mean_confidence=round(mc, 3),
            ))
        return PoseTrack(
            analysis_id=analysis_id, fps=round(seq.fps, 3), frame_count=seq.num_frames,
            width=seq.width, height=seq.height, keypoint_names=list(seq.names),
            skeleton_edges=SKELETON_EDGES, left_indices=LEFT_INDICES,
            right_indices=RIGHT_INDICES, frames=frames,
        )


def _video_exists(path: str) -> bool:
    from pathlib import Path

    return bool(path) and Path(path).exists()


class _DemoCanvas:
    """Stand-in for ``DecodedVideo`` when a demo preset has no real upload.

    Provides an empty BGR canvas of standard size; the simulated estimator draws
    keypoints onto this geometry. fps is fixed at 30 for stable event timing.
    """

    def __init__(self, test_type: TestType, seconds: float = 7.0, fps: float = 30.0,
                 width: int = 1280, height: int = 720):
        n = int(seconds * fps)
        self.frames = np.zeros((n, height, width, 3), dtype=np.uint8)
        self.fps = fps
        self.width = width
        self.height = height
        self.frame_count = n
        self.duration_sec = seconds
        self.rotation = 0
        self.sampled_stride = 1
        self.metadata = {"demo": True}
