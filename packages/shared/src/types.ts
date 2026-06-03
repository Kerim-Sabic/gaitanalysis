/**
 * Shared API contract — mirrors apps/api/app/schemas.py.
 * Keep these in sync; this is the single source of truth for the web client.
 */

export type Sex = "male" | "female" | "other" | "unspecified";

export type TestType =
  | "standard_walk"
  | "timed_up_and_go"
  | "six_minute_walk"
  | "sit_to_stand"
  | "post_op_mobility"
  | "neuro_gait_screen";

export type CameraView = "sagittal" | "coronal" | "unknown";

export type AnalysisStatus = "queued" | "running" | "completed" | "failed";

export type AnalysisMode = "clinical" | "demo";

export type FlagSeverity = "info" | "low" | "moderate" | "high";

export type MetricStatus = "good" | "review" | "limited" | "low_confidence";

export type ReviewStatus = "pending" | "in_review" | "reviewed";

export type DemoPreset = "normal" | "asymmetric" | "poor_quality" | "tug";

export interface PatientCaseCreate {
  patient_code: string;
  age?: number | null;
  sex?: Sex;
  height_cm?: number | null;
  weight_kg?: number | null;
  indication?: string | null;
  clinician?: string | null;
}

export interface PatientCase extends PatientCaseCreate {
  id: string;
  sex: Sex;
  created_at: string;
  last_analysis_at?: string | null;
  last_analysis_id?: string | null;
  review_status: ReviewStatus;
}

export interface CaseSummary {
  case: PatientCase;
  last_risk_band?: string | null;
  last_quality?: number | null;
  last_mode?: string | null;
}

export interface VideoMetadata {
  id: string;
  case_id: string;
  filename: string;
  stored_path: string;
  duration_sec: number;
  fps: number;
  width: number;
  height: number;
  frame_count: number;
  rotation: number;
  upload_time: string;
  test_type: TestType;
  camera_view: CameraView;
  calibration_available: boolean;
  calibration_distance_m?: number | null;
}

export interface QualityResult {
  overall_score: number;
  lighting_score: number;
  blur_score: number;
  resolution_score: number;
  full_body_visibility: number;
  feet_visibility: number;
  camera_stability: number;
  duration_ok: boolean;
  framerate_ok: boolean;
  detected_view: CameraView;
  warnings: string[];
  recommendations: string[];
}

export interface Metric {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  confidence: number;
  status: MetricStatus;
  normal_reference?: string | null;
  interpretation: string;
}

export interface Asymmetry {
  key: string;
  label: string;
  left: number | null;
  right: number | null;
  asymmetry_percent: number | null;
  unit: string;
  confidence: number;
  status: MetricStatus;
  interpretation: string;
}

export interface GaitEvent {
  type: string;
  side?: string | null;
  frame_index: number;
  timestamp: number;
  confidence: number;
}

export interface JointCurvePoint {
  t: number;
  value: number;
}

export interface JointCurve {
  key: string;
  label: string;
  unit: string;
  min: number | null;
  max: number | null;
  rom: number | null;
  samples: JointCurvePoint[];
}

export interface ClinicalFlag {
  name: string;
  severity: FlagSeverity;
  confidence: number;
  explanation: string;
  supporting_metrics: string[];
}

export interface ModelInfo {
  pose_model: string;
  pose_model_version: string;
  analysis_mode: AnalysisMode;
  keypoint_format: string;
  pipeline_version: string;
  frame_count: number;
  fps: number;
  mean_keypoint_confidence: number;
  calibration_status: string;
  notes: string[];
}

export interface AnalysisStageState {
  key: string;
  label: string;
  status: "pending" | "active" | "done" | "error";
}

export interface AnalysisProgress {
  analysis_id: string;
  case_id: string;
  status: AnalysisStatus;
  progress: number;
  current_stage?: string | null;
  stages: AnalysisStageState[];
  error?: string | null;
  updated_at: string;
}

export interface GaitAnalysisResult {
  analysis_id: string;
  case_id: string;
  video_id: string;
  status: AnalysisStatus;
  test_type: TestType;
  analysis_mode: AnalysisMode;
  quality: QualityResult;
  metrics: Metric[];
  asymmetry: Asymmetry[];
  events: GaitEvent[];
  joint_curves: JointCurve[];
  clinical_flags: ClinicalFlag[];
  mobility_risk_support_score: number;
  mobility_risk_band: string;
  overall_confidence: number;
  limitations: string[];
  report_summary: string;
  patient_summary: string;
  recommendations: string[];
  model_info: ModelInfo;
  created_at: string;
}

export interface PoseFrame {
  frame_index: number;
  t: number;
  keypoints: number[][];
  mean_confidence: number;
}

export interface PoseTrack {
  analysis_id: string;
  fps: number;
  frame_count: number;
  width: number;
  height: number;
  keypoint_names: string[];
  skeleton_edges: number[][];
  left_indices: number[];
  right_indices: number[];
  frames: PoseFrame[];
}
