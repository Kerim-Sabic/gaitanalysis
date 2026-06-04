"""Status/verification schemas for the model control plane."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ModelStatus(BaseModel):
    configured_backend: str
    active_backend: str
    available_backends: list[str] = Field(default_factory=list)
    configured_backend_available: bool = False
    any_real_backend_available: bool = False
    demo_mode_available: bool = True
    real_analysis_available: bool = False
    model_loaded: bool = False
    model_verified: bool = False
    model_name: str = ""
    model_file: str = ""
    model_version: str = ""
    device: str = "cpu"
    initialization_error: Optional[str] = None
    inference_test_status: str = "not_run"  # passed | execution_only | failed | not_run
    landmarks_detected: bool = False
    landmark_count: int = 0
    valid_pose_frames: int = 0
    average_confidence: float = 0.0
    last_healthcheck_status: str = "unknown"
    simulated_data_used: bool = False
    backend_availability: dict[str, bool] = Field(default_factory=dict)
    backend_errors: dict[str, str] = Field(default_factory=dict)


class ModelVerifyResult(BaseModel):
    status: str = "failed"  # passed | execution_only | failed
    passed: bool = False
    backend: str = ""
    model_name: str = ""
    model_version: str = ""
    model_file: str = ""
    device: str = "cpu"
    initialized: bool = False
    inference_ran: bool = False
    landmarks_detected: bool = False
    landmark_count: int = 0
    frames_processed: int = 0
    valid_pose_frames: int = 0
    average_confidence: float = 0.0
    sample_used: str = "synthetic"  # path | "synthetic"
    error: Optional[str] = None
    note: str = ""


class HealthcheckResult(BaseModel):
    status: str = "failed"  # passed | execution_only | failed
    passed: bool = False
    checks: dict[str, bool] = Field(default_factory=dict)
    backend: str = ""
    analysis_mode: str = ""
    sample_used: str = "synthetic"
    valid_pose_frames: int = 0
    simulated_data_used: bool = False
    error: Optional[str] = None
    details: list[str] = Field(default_factory=list)
