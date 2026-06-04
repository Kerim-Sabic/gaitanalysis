"""Pipeline orchestrator — wires the modular stages into one analysis run.

    video -> quality -> detection -> pose -> smoothing -> events ->
    metrics -> clinical flags -> narrative/report

HARD real/demo separation:
  * demo presets use the simulated estimator (analysis_mode = demo_simulated);
  * real analysis uses the model loader, which NEVER silently falls back to demo
    — it raises ModelUnavailableError, surfaced here as a clear AnalysisError.

Per-metric confidence is derived from the tracking quality of the keypoints each
metric actually depends on (see keypoint_quality.py), not a generic score.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from app.config import get_settings
from app.pipeline.events import GaitEventDetector
from app.pipeline.flags import ClinicalFlagService
from app.pipeline.keypoint_quality import (
    RELATED_METRICS,
    KeypointQualityIndex,
    compute_keypoint_stats,
)
from app.pipeline.metrics import GaitMetricsCalculator
from app.pipeline.narrative import NarrativeGenerator
from app.pipeline.quality import QualityAssessmentService
from app.pipeline.smoothing import TemporalSmoothingService
from app.pipeline.tracking import PersonDetectionService
from app.pipeline.video_processor import VideoError, VideoProcessor
from app.schemas import (
    AnalysisMode,
    AnalysisStatus,
    GaitAnalysisResult,
    KeypointSource,
    Metric,
    MetricStatus,
    ModelInfo,
    PatientCase,
    PoseFrame,
    PoseTrack,
    TestType,
    VideoMetadata,
)

PIPELINE_VERSION = "0.2.0"

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

# Which keypoints each metric depends on (used to derive confidence + provenance).
METRIC_SOURCE_KEYPOINTS: dict[str, list[str]] = {
    "cadence_steps_per_min": ["left_ankle", "right_ankle", "left_heel", "right_heel"],
    "step_count": ["left_ankle", "right_ankle"],
    "gait_cycles_detected": ["left_ankle", "right_ankle"],
    "walking_speed_m_per_s": ["left_hip", "right_hip", "left_ankle", "right_ankle"],
    "stride_length_m": ["left_hip", "right_hip", "left_ankle", "right_ankle"],
    "left_step_time_sec": ["left_ankle", "right_ankle", "left_heel"],
    "right_step_time_sec": ["left_ankle", "right_ankle", "right_heel"],
    "left_stride_time_sec": ["left_ankle", "left_heel"],
    "right_stride_time_sec": ["right_ankle", "right_heel"],
    "knee_rom_left_deg": ["left_hip", "left_knee", "left_ankle"],
    "knee_rom_right_deg": ["right_hip", "right_knee", "right_ankle"],
    "hip_rom_left_deg": ["left_shoulder", "left_hip", "left_knee"],
    "hip_rom_right_deg": ["right_shoulder", "right_hip", "right_knee"],
    "trunk_sway_index": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "stride_time_variability": ["left_ankle", "right_ankle"],
}

# Foot-keypoint edges added to the overlay when extended keypoints are present.
_FOOT_EDGES = {
    "left": [("left_ankle", "left_heel"), ("left_heel", "left_foot_index"),
             ("left_ankle", "left_foot_index")],
    "right": [("right_ankle", "right_heel"), ("right_heel", "right_foot_index"),
              ("right_ankle", "right_foot_index")],
}


class AnalysisError(Exception):
    def __init__(self, message: str, code: str = "analysis_failed"):
        super().__init__(message)
        self.code = code


@dataclass
class AnalysisOutput:
    result: GaitAnalysisResult
    pose_track: PoseTrack


def _backend_label(mode: AnalysisMode) -> str:
    return {
        AnalysisMode.real_mediapipe_tasks: "mediapipe_tasks",
        AnalysisMode.real_ultralytics_pose: "ultralytics_pose",
        AnalysisMode.real_mediapipe: "mediapipe_tasks",
        AnalysisMode.real_mmpose: "mmpose",
        AnalysisMode.demo_simulated: "demo",
        AnalysisMode.failed: "none",
    }.get(mode, "unknown")


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
        t0 = time.perf_counter()

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
        _t_decode = time.perf_counter()
        timings_ms: dict[str, float] = {"decode_ms": round((_t_decode - t0) * 1000.0, 1)}

        # 2) Pose estimation — HARD real/demo separation (see module docstring).
        if demo_preset:
            from app.pipeline.pose.simulated import SimulatedPoseEstimator

            estimator = SimulatedPoseEstimator.from_preset(demo_preset)
            mode = AnalysisMode.demo_simulated
        else:
            from app.models.model_loader import ModelUnavailableError, get_model_loader

            try:
                estimator, mode = get_model_loader().get_real_estimator()
            except ModelUnavailableError as e:
                raise AnalysisError(str(e), code="model_unavailable") from e

        try:
            seq = estimator.estimate_2d_pose(decoded.frames, decoded.fps)
        except AnalysisError:
            raise
        except Exception as e:
            raise AnalysisError(f"Pose inference failed: {e}", code="inference_failed") from e
        if seq.num_frames == 0:
            raise AnalysisError("No frames available for pose estimation.", "no_person")
        _t_infer = time.perf_counter()
        timings_ms["inference_ms"] = round((_t_infer - _t_decode) * 1000.0, 1)
        from app.models import model_registry

        selected_backend = (
            getattr(estimator, "selected_backend", "")
            or getattr(estimator, "backend_id", "")
            or _backend_label(mode)
        )
        mode = model_registry.analysis_mode_for_backend(selected_backend)

        # 2a) Demo runs: render the simulated subject into REAL frames so quality
        #     scoring is genuine and a playable clip is produced.
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

        # 4) Quality (raw frames + pose coverage).
        quality = self.quality_svc.assess(decoded, smoothed)
        helper_models, helper_limitations = _run_optional_helpers(
            decoded.frames, quality, settings, is_demo=mode == AnalysisMode.demo_simulated
        )

        # 4b) Per-keypoint tracking-quality stats (real, from the keypoints).
        keypoint_stats = compute_keypoint_stats(smoothed)
        kp_index = KeypointQualityIndex.from_stats(keypoint_stats)
        from app.pipeline.pose.quality_comparator import score_pose_sequence

        backend_scores = dict(getattr(estimator, "backend_scores", {}))
        selected_score = backend_scores.get(selected_backend)
        if selected_score is None:
            selected_score = score_pose_sequence(smoothed, backend=selected_backend)
            backend_scores[selected_backend] = selected_score
        backend_quality = float(selected_score.get("final_score", 0.0)) / 100.0

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

        # 6b) Derive each metric's confidence from its source keypoints' quality.
        info = estimator.get_model_info()
        is_simulated = mode == AnalysisMode.demo_simulated
        event_consistency = _event_consistency(bundle)
        _refine_metric_confidence(
            bundle.metrics, kp_index, quality.overall_score,
            calibration_status=bundle.calibration_status,
            event_consistency=event_consistency,
            model_name=info.name, mode=mode, limitations=bundle.limitations,
            source_backend=selected_backend, backend_quality=backend_quality,
        )
        overall_conf = (
            round(float(np.mean([m.confidence for m in bundle.metrics])), 3)
            if bundle.metrics else bundle.overall_confidence
        )

        # 7) Flags + narrative.
        flags = self.flag_svc.generate(bundle, quality)
        narrative = self.narrator.generate(bundle, quality, flags, test_type, mode)

        # Model provenance.
        all_scores = smoothed.all_keypoints()[..., 2]
        frame_mean = np.nanmean(all_scores, axis=1) if all_scores.size else np.asarray([])
        valid_pose_frames = int(np.sum(frame_mean > 0.3))
        failed_frames = max(0, smoothed.num_frames - valid_pose_frames)
        lowest = sorted(keypoint_stats, key=lambda s: s.mean_confidence)[:3]
        timings_ms["postprocess_ms"] = round((time.perf_counter() - _t_infer) * 1000.0, 1)
        timings_ms["total_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        backend_failures = dict(getattr(estimator, "backend_failures", {}))
        from app.pipeline.pose.mmpose_adapter import MMPoseRTMWPoseEstimator

        mmpose_error = MMPoseRTMWPoseEstimator.availability_error()
        mmpose_status = (
            "WORKING" if selected_backend == "mmpose_rtmw"
            else ("AVAILABLE_NOT_SELECTED" if mmpose_error is None else _helper_blocked_status(mmpose_error))
        )
        helper_models["mmpose"] = {
            "model": "MMPose RTMW whole-body pose",
            "status": mmpose_status,
            "used_in_analysis": selected_backend == "mmpose_rtmw",
            "error": mmpose_error or "",
        }
        try:
            from app.pipeline.pose.wham_adapter import WHAMAdapter

            wham_info = WHAMAdapter.status()
            wham_status = str(wham_info["status"])
            helper_models["wham"] = wham_info
        except Exception:
            wham_status = "BLOCKED_RUNTIME"
        sam2_status = str(helper_models["sam2"]["status"])
        depth_status = str(helper_models["depth"]["status"])
        model_info = ModelInfo(
            pose_model=info.name,
            pose_model_version=info.version,
            pose_backend=selected_backend,
            analysis_mode=mode,
            keypoint_format=info.keypoint_format,
            keypoint_source=(
                KeypointSource.simulated.value if is_simulated
                else KeypointSource.real_video_inference.value
            ),
            pipeline_version=PIPELINE_VERSION,
            model_loaded=not is_simulated,
            model_verified=(not is_simulated) and valid_pose_frames > 0,
            device=str(getattr(estimator, "device", "cpu")),
            frame_count=smoothed.num_frames,
            valid_pose_frames=valid_pose_frames,
            failed_frames=failed_frames,
            fps=round(smoothed.fps, 2),
            mean_keypoint_confidence=round(smoothed.mean_confidence, 3),
            lowest_confidence_keypoints=[s.name for s in lowest],
            interpolation_used=bool(
                smoothed.interpolated_mask is not None and np.any(smoothed.interpolated_mask)
            ),
            processing_time_sec=round(time.perf_counter() - t0, 3),
            timings_ms=timings_ms,
            simulated_data_used=is_simulated,
            calibration_status=bundle.calibration_status,
            notes=info.notes + helper_limitations,
            selected_backend=selected_backend,
            selection_reason=getattr(
                estimator, "selection_reason",
                f"Explicitly configured real backend: {selected_backend}.",
            ),
            backend_scores=backend_scores,
            backend_failures=backend_failures,
            model_limitations=list(getattr(estimator, "model_limitations", info.notes)),
            foot_landmarks_available=all(
                name in smoothed.all_names()
                for name in ("left_heel", "right_heel", "left_foot_index", "right_foot_index")
            ),
            mmpose_status=mmpose_status,
            sam2_status=sam2_status,
            segmentation_status=sam2_status,
            depth_status=depth_status,
            wham_status=wham_status,
            helper_models=helper_models,
        )
        result_limitations = bundle.limitations + (events.notes or []) + helper_limitations
        if wham_status != "WORKING":
            result_limitations.append(
                "Single-camera 2D analysis: optional WHAM 3D reconstruction was not active."
            )
        if smoothed.mean_confidence < 0.35:
            result_limitations.append(
                "Mean pose confidence is below 0.35; results are shown with low-confidence warnings."
            )

        result = GaitAnalysisResult(
            analysis_id=analysis_id,
            case_id=case.id,
            video_id=video.id,
            status=AnalysisStatus.completed,
            test_type=test_type,
            analysis_mode=mode,
            pose_backend=selected_backend,
            keypoint_source=model_info.keypoint_source,
            simulated_data_used=is_simulated,
            quality=quality,
            metrics=bundle.metrics,
            asymmetry=bundle.asymmetry,
            events=events.events,
            joint_curves=bundle.joint_curves,
            keypoint_stats=keypoint_stats,
            clinical_flags=flags,
            mobility_risk_support_score=bundle.risk_score,
            mobility_risk_band=bundle.risk_band,
            overall_confidence=overall_conf,
            limitations=result_limitations,
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
        names = seq.all_names()
        kp = seq.all_keypoints()
        name_to_idx = {n: i for i, n in enumerate(names)}
        mask = seq.interpolated_mask

        from app.pipeline.pose.base import SKELETON_EDGES

        edges = [list(e) for e in SKELETON_EDGES]
        for side in ("left", "right"):
            for a, b in _FOOT_EDGES[side]:
                if a in name_to_idx and b in name_to_idx:
                    edges.append([name_to_idx[a], name_to_idx[b]])
        left_idx = [i for i, n in enumerate(names) if n.startswith("left_")]
        right_idx = [i for i, n in enumerate(names) if n.startswith("right_")]

        frames: list[PoseFrame] = []
        for i in range(seq.num_frames):
            pts = [
                [
                    round(float(x), 1) if np.isfinite(x) else 0.0,
                    round(float(y), 1) if np.isfinite(y) else 0.0,
                    round(float(s), 3) if np.isfinite(s) else 0.0,
                ]
                for x, y, s in kp[i]
            ]
            mc = float(np.nanmean(kp[i, :, 2]))
            interp = (
                [j for j in range(kp.shape[1]) if mask is not None and mask.shape[1] > j and mask[i, j]]
            )
            frames.append(PoseFrame(
                frame_index=i, t=round(float(seq.timestamps[i]), 3),
                keypoints=pts, mean_confidence=round(mc, 3), interp=interp,
            ))
        return PoseTrack(
            analysis_id=analysis_id, fps=round(seq.fps, 3), frame_count=seq.num_frames,
            width=seq.width, height=seq.height, keypoint_names=names,
            skeleton_edges=edges, left_indices=left_idx, right_indices=right_idx,
            frames=frames,
        )


# --------------------------------------------------------------------------- #
def _run_optional_helpers(frames, quality, settings, *, is_demo: bool) -> tuple[dict, list[str]]:
    """Run explicitly enabled advanced helpers without making pose analysis fragile."""
    helpers: dict[str, dict] = {}
    limitations: list[str] = []

    from app.pipeline.segmentation.sam2_adapter import SAM2Segmenter

    sam2 = SAM2Segmenter()
    if is_demo:
        helpers["sam2"] = {
            **sam2.status(),
            "status": "NOT_RUN_DEMO",
            "used_in_analysis": False,
            "error": "Advanced helpers are not run on simulated demo data.",
        }
    elif not settings.enable_sam2:
        helpers["sam2"] = {
            **sam2.status(),
            "used_in_analysis": False,
        }
    else:
        try:
            sam2.segment_person(_sample_helper_frames(frames, settings.sam2_max_frames))
            helpers["sam2"] = {
                **sam2.status(),
                "used_in_analysis": True,
                "purpose": "Segmentation-assisted capture quality",
            }
            limitations.append(
                "SAM2 capture-quality metadata is derived from sampled-frame segmentation; "
                "masks are not propagated across every video frame."
            )
            full_body = float(sam2.last_metadata.get("full_body_visibility_estimate", 0))
            feet = float(sam2.last_metadata.get("feet_region_visibility_estimate", 0))
            if full_body < 0.7:
                quality.warnings.append(
                    "SAM2 person masks indicate the full body may not be consistently visible."
                )
            if feet < 0.1:
                quality.warnings.append(
                    "SAM2 person masks indicate limited visibility in the feet region."
                )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            helpers["sam2"] = {
                **sam2.status(),
                "status": (
                    "DOCKER_REQUIRED"
                    if settings.advanced_models_require_docker
                    else "BLOCKED_RUNTIME"
                ),
                "used_in_analysis": False,
                "error": error,
            }
            limitations.append(f"SAM2 segmentation helper was enabled but unavailable: {error}")

    from app.pipeline.depth.depth_anything_adapter import (
        LIMITATION as DEPTH_LIMITATION,
        DepthAnythingV2Adapter,
    )

    depth = DepthAnythingV2Adapter()
    if is_demo:
        helpers["depth"] = {
            **depth.status(),
            "status": "NOT_RUN_DEMO",
            "used_in_analysis": False,
            "error": "Advanced helpers are not run on simulated demo data.",
        }
    elif not settings.enable_depth:
        helpers["depth"] = {
            **depth.status(),
            "used_in_analysis": False,
        }
    else:
        try:
            depth.estimate_relative_depth(_sample_helper_frames(frames, settings.depth_max_frames))
            helpers["depth"] = {
                **depth.status(),
                "used_in_analysis": True,
                "purpose": "Relative-depth scene metadata",
            }
            limitations.append(DEPTH_LIMITATION)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            helpers["depth"] = {
                **depth.status(),
                "status": (
                    "DOCKER_REQUIRED"
                    if settings.advanced_models_require_docker
                    else "BLOCKED_RUNTIME"
                ),
                "used_in_analysis": False,
                "error": error,
            }
            limitations.append(f"Depth Anything V2 helper was enabled but unavailable: {error}")

    return helpers, limitations


def _sample_helper_frames(frames, limit: int):
    if len(frames) <= max(1, limit):
        return frames
    indices = np.unique(np.linspace(0, len(frames) - 1, max(1, limit)).astype(int))
    return frames[indices]


def _helper_blocked_status(error: str) -> str:
    lowered = error.lower()
    if "mmcv._ext" in lowered or "compiled mmcv" in lowered:
        return "DOCKER_REQUIRED"
    if "licensed" in lowered or "smpl_neutral.pkl" in lowered:
        return "BLOCKED_LICENSED_ASSETS"
    if "config" in lowered:
        return "BLOCKED_CONFIG"
    if "checkpoint" in lowered or "weight" in lowered:
        return "BLOCKED_WEIGHT"
    if any(name in lowered for name in ("dependency", "not installed", "module", "import")):
        return "BLOCKED_DEPENDENCY"
    return "BLOCKED_RUNTIME"


def _event_consistency(bundle) -> float:
    cv = getattr(bundle, "stride_cv", None)
    cycles = next((m.value for m in bundle.metrics if m.key == "gait_cycles_detected"), 0) or 0
    cyc_factor = min(1.0, cycles / 4.0)
    cv_factor = 1.0 if cv is None else max(0.3, 1.0 - min(cv, 0.3) / 0.3)
    return float(max(0.3, min(1.0, 0.5 * cyc_factor + 0.5 * cv_factor)))


def _refine_metric_confidence(
    metrics: list[Metric],
    kp_index: KeypointQualityIndex,
    quality_score: float,
    *,
    calibration_status: str,
    event_consistency: float,
    model_name: str,
    mode: AnalysisMode,
    limitations: list[str],
    source_backend: str,
    backend_quality: float,
) -> None:
    """Recompute each metric's confidence from the tracking quality of its source
    keypoints, and attach provenance. Never inflates confidence for weak keypoints."""
    for m in metrics:
        sources = METRIC_SOURCE_KEYPOINTS.get(m.key, RELATED_METRICS_INVERSE.get(m.key, []))
        m.source_keypoints = sources
        m.source_model = model_name
        m.source_backend = source_backend
        m.selected_model = model_name
        m.analysis_mode = mode
        m.limitations = list(limitations)
        if not sources:
            m.confidence_reason = "Structural metric; confidence reflects video quality."
            continue
        cal = 1.0
        if m.key in ("walking_speed_m_per_s", "stride_length_m"):
            cal = (1.0 if calibration_status == "distance-calibrated"
                   else 0.7 if calibration_status == "height-calibrated" else 0.5)
        conf, reason = kp_index.metric_confidence(
            sources, quality_score=quality_score, calibration_factor=cal,
            event_consistency=event_consistency,
        )
        conf = round(conf * (0.75 + 0.25 * max(0.0, min(1.0, backend_quality))), 3)
        if m.value is None:
            m.confidence = 0.0
            m.status = MetricStatus.limited
        else:
            m.confidence = conf
            if conf < 0.45 and m.status != MetricStatus.limited:
                m.status = MetricStatus.low_confidence
        m.confidence_reason = (
            f"{reason} Backend gait-quality score {backend_quality:.0%} "
            f"({source_backend})."
        )


# Allow keypoints in keypoint_quality.RELATED_METRICS to also drive sources if a
# metric isn't in METRIC_SOURCE_KEYPOINTS (kept consistent with that module).
RELATED_METRICS_INVERSE: dict[str, list[str]] = {}
for _kp, _metrics in RELATED_METRICS.items():
    for _mk in _metrics:
        RELATED_METRICS_INVERSE.setdefault(_mk, []).append(_kp)


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
