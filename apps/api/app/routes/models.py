"""Model control-plane endpoints: status, verification, healthcheck."""
from __future__ import annotations

from fastapi import APIRouter

from app.models.model_loader import get_model_loader
from app.models.model_status import HealthcheckResult, ModelStatus, ModelVerifyResult
from app.schemas import ModelCapabilities
from app.services.model_capabilities import build_capabilities

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status", response_model=ModelStatus)
def models_status() -> ModelStatus:
    return get_model_loader().status()


@router.get("/capabilities", response_model=ModelCapabilities)
def models_capabilities() -> ModelCapabilities:
    """Live model cards for the pre-analysis setup flow (pose backends + helpers
    + quality modes). Status is computed from the runtime — the frontend renders
    cards from this and must not hardcode availability."""
    return build_capabilities()


@router.get("/verify", response_model=ModelVerifyResult)
def models_verify() -> ModelVerifyResult:
    """Run a lightweight real-inference verification on a generated frame."""
    return get_model_loader().verify()


@router.get("/healthcheck", response_model=HealthcheckResult)
def models_healthcheck() -> HealthcheckResult:
    """Full backend health check across the real-analysis chain."""
    return get_model_loader().healthcheck()
