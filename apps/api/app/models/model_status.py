"""Status/verification schemas for the model control plane."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ModelStatus(BaseModel):
    active_backend: str
    available_backends: list[str] = Field(default_factory=list)
    model_loaded: bool = False
    model_name: str = ""
    model_version: str = ""
    device: str = "cpu"
    initialization_error: Optional[str] = None
    last_healthcheck_status: str = "unknown"  # passed | failed | unknown
    demo_mode_available: bool = True
    real_analysis_available: bool = False


class ModelVerifyResult(BaseModel):
    passed: bool = False
    backend: str = ""
    model_name: str = ""
    model_version: str = ""
    device: str = "cpu"
    initialized: bool = False
    inference_ran: bool = False
    landmarks_detected: bool = False
    landmark_count: int = 0
    average_confidence: float = 0.0
    error: Optional[str] = None
    note: str = ""


class HealthcheckResult(BaseModel):
    passed: bool = False
    checks: dict[str, bool] = Field(default_factory=dict)
    backend: str = ""
    analysis_mode: str = ""
    simulated_data_used: bool = False
    error: Optional[str] = None
    details: list[str] = Field(default_factory=list)
