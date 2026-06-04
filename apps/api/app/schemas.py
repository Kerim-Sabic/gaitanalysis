"""Pydantic schemas — the typed contract shared across the API and pipeline.

These mirror the TypeScript types in ``packages/shared`` so the frontend and
backend speak the same language.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    unspecified = "unspecified"


class TestType(str, Enum):
    standard_walk = "standard_walk"
    timed_up_and_go = "timed_up_and_go"
    six_minute_walk = "six_minute_walk"
    sit_to_stand = "sit_to_stand"
    post_op_mobility = "post_op_mobility"
    neuro_gait_screen = "neuro_gait_screen"


class CameraView(str, Enum):
    sagittal = "sagittal"  # side view
    coronal = "coronal"  # front/back view
    unknown = "unknown"


class AnalysisStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class AnalysisMode(str, Enum):
    real_mediapipe_tasks = "real_mediapipe_tasks"  # MediaPipe Tasks PoseLandmarker
    real_ultralytics_pose = "real_ultralytics_pose"  # Ultralytics YOLO-Pose (COCO-17)
    real_mediapipe = "real_mediapipe"  # legacy/general real MediaPipe label
    real_mmpose = "real_mmpose"  # real MMPose/RTMPose inference on real frames
    demo_simulated = "demo_simulated"  # simulated keypoints — NOT real patient analysis
    failed = "failed"  # model/inference failed; no metrics produced
    # Compatibility aliases (same value -> resolve to the canonical members above)
    # so older code paths using `.demo` / `.clinical` keep working.
    demo = "demo_simulated"
    clinical = "real_mediapipe"

    @property
    def is_real(self) -> bool:
        return self in (
            AnalysisMode.real_mediapipe_tasks,
            AnalysisMode.real_ultralytics_pose,
            AnalysisMode.real_mediapipe,
            AnalysisMode.real_mmpose,
        )

    @classmethod
    def _missing_(cls, value):
        # Back-compat for results persisted before the provenance-specific values.
        return {"demo": cls.demo_simulated, "clinical": cls.real_mediapipe}.get(value)


class KeypointSource(str, Enum):
    real_video_inference = "real_video_inference"
    simulated = "simulated"
    none = "none"


class FlagSeverity(str, Enum):
    info = "info"
    low = "low"
    moderate = "moderate"
    high = "high"


class MetricStatus(str, Enum):
    good = "good"
    review = "review"
    limited = "limited"
    low_confidence = "low_confidence"


class ReviewStatus(str, Enum):
    pending = "pending"
    in_review = "in_review"
    reviewed = "reviewed"


# --------------------------------------------------------------------------- #
# Cases & video
# --------------------------------------------------------------------------- #
class PatientCaseCreate(BaseModel):
    patient_code: str = Field(..., description="De-identified patient code or initials")
    age: Optional[int] = Field(None, ge=0, le=120)
    sex: Sex = Sex.unspecified
    height_cm: Optional[float] = Field(None, gt=30, lt=260)
    weight_kg: Optional[float] = Field(None, gt=2, lt=400)
    indication: Optional[str] = None
    clinician: Optional[str] = None


class PatientCase(PatientCaseCreate):
    id: str
    created_at: datetime = Field(default_factory=_now)
    last_analysis_at: Optional[datetime] = None
    last_analysis_id: Optional[str] = None
    review_status: ReviewStatus = ReviewStatus.pending


class VideoMetadata(BaseModel):
    id: str
    case_id: str
    filename: str
    stored_path: str
    duration_sec: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    frame_count: int = 0
    rotation: int = 0
    upload_time: datetime = Field(default_factory=_now)
    test_type: TestType = TestType.standard_walk
    camera_view: CameraView = CameraView.unknown
    calibration_available: bool = False
    calibration_distance_m: Optional[float] = None


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
class QualityResult(BaseModel):
    overall_score: float = Field(..., ge=0, le=100)
    lighting_score: float = Field(..., ge=0, le=100)
    blur_score: float = Field(..., ge=0, le=100)
    resolution_score: float = Field(..., ge=0, le=100)
    full_body_visibility: float = Field(..., ge=0, le=100)
    feet_visibility: float = Field(..., ge=0, le=100)
    camera_stability: float = Field(..., ge=0, le=100)
    duration_ok: bool = True
    framerate_ok: bool = True
    detected_view: CameraView = CameraView.unknown
    status: str = "PASS_WITH_LIMITATIONS"
    pose_valid_percentage: float = Field(0.0, ge=0, le=100)
    person_size_percent: float = Field(0.0, ge=0, le=100)
    ankle_confidence: float = Field(0.0, ge=0, le=1)
    heel_confidence: float = Field(0.0, ge=0, le=1)
    foot_index_confidence: float = Field(0.0, ge=0, le=1)
    multi_person_risk: float = Field(0.0, ge=0, le=1)
    occlusion_missing_percentage: float = Field(0.0, ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Metrics, events, curves, flags
# --------------------------------------------------------------------------- #
class Metric(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    unit: str = ""
    confidence: float = Field(0.0, ge=0, le=1)
    status: MetricStatus = MetricStatus.limited
    normal_reference: Optional[str] = None
    interpretation: str = ""
    # Provenance — confidence is derived from these, not generic.
    source_keypoints: list[str] = Field(default_factory=list)
    source_model: str = ""
    source_backend: str = ""
    selected_model: str = ""
    analysis_mode: Optional[AnalysisMode] = None
    limitations: list[str] = Field(default_factory=list)
    confidence_reason: str = ""


class Asymmetry(BaseModel):
    key: str
    label: str
    left: Optional[float] = None
    right: Optional[float] = None
    asymmetry_percent: Optional[float] = None
    unit: str = ""
    confidence: float = Field(0.0, ge=0, le=1)
    status: MetricStatus = MetricStatus.limited
    interpretation: str = ""


class GaitEvent(BaseModel):
    type: str  # heel_strike | toe_off | turn_start | turn_end | stand | sit
    side: Optional[str] = None  # left | right
    frame_index: int
    timestamp: float
    confidence: float = 0.0


class JointCurvePoint(BaseModel):
    t: float
    value: float


class JointCurve(BaseModel):
    key: str  # knee_left | knee_right | hip_left | hip_right | trunk | ...
    label: str
    unit: str = "deg"
    min: Optional[float] = None
    max: Optional[float] = None
    rom: Optional[float] = None
    samples: list[JointCurvePoint] = Field(default_factory=list)


class ClinicalFlag(BaseModel):
    name: str
    severity: FlagSeverity
    confidence: float = Field(0.0, ge=0, le=1)
    explanation: str
    supporting_metrics: list[str] = Field(default_factory=list)


class KeypointStat(BaseModel):
    name: str
    side: str  # left | right | midline
    index: int
    mean_confidence: float = 0.0
    valid_frame_percent: float = 0.0
    missing_frame_percent: float = 0.0
    interpolated_percent: float = 0.0
    quality_band: str = "unreliable"  # good | moderate | limited | unreliable
    related_metrics: list[str] = Field(default_factory=list)
    note: str = ""


class ModelInfo(BaseModel):
    pose_model: str
    pose_model_version: str
    pose_backend: str = "unknown"
    analysis_mode: AnalysisMode
    keypoint_format: str
    keypoint_source: str = KeypointSource.none.value
    pipeline_version: str
    model_loaded: bool = False
    model_verified: bool = False
    device: str = "cpu"
    frame_count: int = 0
    valid_pose_frames: int = 0
    failed_frames: int = 0
    fps: float = 0.0
    mean_keypoint_confidence: float = 0.0
    lowest_confidence_keypoints: list[str] = Field(default_factory=list)
    interpolation_used: bool = False
    processing_time_sec: float = 0.0
    timings_ms: dict[str, float] = Field(default_factory=dict)  # decode/inference/postprocess/total
    simulated_data_used: bool = False
    calibration_status: str = "uncalibrated"
    clinical_validation_status: str = "Not yet validated — clinician review required"
    notes: list[str] = Field(default_factory=list)
    selected_backend: str = ""
    selection_reason: str = ""
    backend_scores: dict[str, dict] = Field(default_factory=dict)
    backend_failures: dict[str, str] = Field(default_factory=dict)
    model_limitations: list[str] = Field(default_factory=list)
    foot_landmarks_available: bool = False
    segmentation_status: str = "not_run"
    mmpose_status: str = "not_run"
    sam2_status: str = "not_run"


# --------------------------------------------------------------------------- #
# Analysis result + progress
# --------------------------------------------------------------------------- #
class AnalysisStageState(BaseModel):
    key: str
    label: str
    status: str = "pending"  # pending | active | done | error


class AnalysisProgress(BaseModel):
    analysis_id: str
    case_id: str
    status: AnalysisStatus
    progress: float = Field(0.0, ge=0, le=1)
    current_stage: Optional[str] = None
    stages: list[AnalysisStageState] = Field(default_factory=list)
    error: Optional[str] = None
    updated_at: datetime = Field(default_factory=_now)


class GaitAnalysisResult(BaseModel):
    analysis_id: str
    case_id: str
    video_id: str
    status: AnalysisStatus
    test_type: TestType
    analysis_mode: AnalysisMode
    pose_backend: str = "unknown"
    keypoint_source: str = KeypointSource.none.value
    simulated_data_used: bool = False

    quality: QualityResult
    metrics: list[Metric] = Field(default_factory=list)
    asymmetry: list[Asymmetry] = Field(default_factory=list)
    events: list[GaitEvent] = Field(default_factory=list)
    joint_curves: list[JointCurve] = Field(default_factory=list)
    keypoint_stats: list[KeypointStat] = Field(default_factory=list)
    clinical_flags: list[ClinicalFlag] = Field(default_factory=list)

    mobility_risk_support_score: float = Field(0.0, ge=0, le=100)
    mobility_risk_band: str = "review"
    overall_confidence: float = Field(0.0, ge=0, le=1)

    limitations: list[str] = Field(default_factory=list)
    report_summary: str = ""
    patient_summary: str = ""
    recommendations: list[str] = Field(default_factory=list)

    model_info: ModelInfo
    created_at: datetime = Field(default_factory=_now)

    # Convenience accessor used by reporting code.
    def metric(self, key: str) -> Optional[Metric]:
        return next((m for m in self.metrics if m.key == key), None)


# --------------------------------------------------------------------------- #
# Pose track (served separately to the frontend overlay canvas)
# --------------------------------------------------------------------------- #
class PoseFrame(BaseModel):
    frame_index: int
    t: float
    keypoints: list[list[float]]  # [[x, y, score], ...] in pixel coordinates
    mean_confidence: float = 0.0
    interp: list[int] = Field(default_factory=list)  # interpolated keypoint indices


class PoseTrack(BaseModel):
    analysis_id: str
    fps: float
    frame_count: int
    width: int
    height: int
    keypoint_names: list[str]
    skeleton_edges: list[list[int]]
    left_indices: list[int]
    right_indices: list[int]
    frames: list[PoseFrame]


class StartAnalysisRequest(BaseModel):
    video_id: str
    test_type: Optional[TestType] = None
    demo_preset: Optional[str] = None  # normal | asymmetric | poor_quality | tug


class CreateDemoRequest(BaseModel):
    preset: str = "normal"  # normal | asymmetric | poor_quality | tug
    patient_code: Optional[str] = None
