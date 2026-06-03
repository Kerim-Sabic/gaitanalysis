"""Horalix Gait AI — FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.pipeline.pose.mediapipe_adapter import MediaPipePoseEstimator
from app.pipeline.pose.mmpose_adapter import MMPosePoseEstimator
from app.routes import analysis, cases, videos

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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(videos.router)
app.include_router(analysis.router)


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
    return {
        "status": "healthy",
        "pose_backend_pref": settings.pose_backend,
        "models": {
            "mmpose_available": MMPosePoseEstimator.is_available(),
            "mediapipe_available": MediaPipePoseEstimator.is_available(),
            "simulated_fallback": True,
        },
        "demo_mode": settings.allow_demo_mode,
    }
