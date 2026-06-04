"""Horalix Gait AI — FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.pipeline.pose.mediapipe_adapter import MediaPipePoseEstimator
from app.pipeline.pose.mmpose_adapter import MMPosePoseEstimator
from app.routes import analysis, cases, live, models, videos

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Markerless AI gait-analysis backend. AI-assisted gait quantification "
        "for clinician review — not a standalone diagnostic tool."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(videos.router)
app.include_router(analysis.router)
app.include_router(models.router)
app.include_router(live.router)


@app.get("/", tags=["meta"])
def root():
    return {
        "name": settings.app_name,
        "version": settings.version,
        "status": "ok",
        "disclaimer": (
            "AI-assisted gait quantification for clinician review. "
            "Not a standalone diagnostic decision."
        ),
    }


@app.get("/health", tags=["meta"])
def health():
    from app.models.model_loader import get_model_loader

    status = get_model_loader().status()
    return {
        "status": "healthy",
        "pose_backend_pref": settings.pose_backend,
        "models": {
            "mmpose_available": MMPosePoseEstimator.is_available(),
            "mediapipe_available": MediaPipePoseEstimator.is_available(),
            "real_analysis_available": status.real_analysis_available,
            "active_backend": status.active_backend,
        },
        "demo_mode": settings.allow_demo_mode,
    }
