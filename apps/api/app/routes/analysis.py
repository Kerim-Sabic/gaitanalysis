"""Analysis lifecycle: start, poll, fetch result/pose, exports, demo."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.config import get_settings
from app.reporting import build_pdf_report, render_overlay_video
from app.schemas import (
    AnalysisProgress,
    CreateDemoRequest,
    GaitAnalysisResult,
    PatientCase,
    PoseTrack,
    PreflightRequest,
    PreflightResponse,
    StartAnalysisRequest,
    TestType,
    VideoMetadata,
)
from app.services.analysis_service import get_analysis_service
from app.services.model_capabilities import build_preflight
from app.storage import get_storage

router = APIRouter(prefix="/analysis", tags=["analysis"])

DEMO_PRESETS = {"normal", "asymmetric", "poor_quality", "tug"}


@router.post("/preflight", response_model=PreflightResponse)
def preflight(payload: PreflightRequest) -> PreflightResponse:
    """Resolve the chosen setup into an executable plan: what will run, blocked
    reasons, warnings, estimated runtime, and expected model transparency."""
    return build_preflight(payload)


@router.post("/start", response_model=AnalysisProgress)
def start_analysis(payload: StartAnalysisRequest) -> AnalysisProgress:
    storage = get_storage()
    service = get_analysis_service()

    video = storage.get_video(payload.video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    case = storage.get_case(video.case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if payload.demo_preset and payload.demo_preset not in DEMO_PRESETS:
        raise HTTPException(400, f"Unknown demo preset. Allowed: {sorted(DEMO_PRESETS)}")

    # Fail fast for REAL analysis when no real model is available — never silently
    # fall back to demo. The UI offers an explicit "Use Demo Mode Instead" action.
    if not payload.demo_preset:
        from app.models.model_loader import get_model_loader

        status = get_model_loader().status()
        if not status.real_analysis_available:
            raise HTTPException(
                422,
                detail={
                    "message": "Real pose model is unavailable. Run model setup or "
                               "switch to Demo Mode.",
                    "code": "model_unavailable",
                    "initialization_error": status.initialization_error,
                    "demo_mode_available": status.demo_mode_available,
                },
            )

    test_type = payload.test_type or (payload.options.protocol if payload.options else None) \
        or video.test_type
    progress = service.create_job(case.id)
    service.submit(progress, case, video, test_type, payload.demo_preset, options=payload.options)
    return progress


@router.post("/demo", response_model=AnalysisProgress)
def start_demo(payload: CreateDemoRequest) -> AnalysisProgress:
    """One-click demo: creates a de-identified case + virtual video and runs the
    real pipeline on simulated keypoints for the chosen preset."""
    settings = get_settings()
    if not settings.allow_demo_mode:
        raise HTTPException(403, "Demo mode is disabled.")
    if payload.preset not in DEMO_PRESETS:
        raise HTTPException(400, f"Unknown demo preset. Allowed: {sorted(DEMO_PRESETS)}")

    storage = get_storage()
    service = get_analysis_service()

    preset_meta = {
        "normal": ("DEMO-NRM", "Healthy reference walk", TestType.standard_walk, 34),
        "asymmetric": ("DEMO-ASY", "Asymmetric gait pattern", TestType.standard_walk, 67),
        "poor_quality": ("DEMO-LOWQ", "Low-quality capture", TestType.standard_walk, 58),
        "tug": ("DEMO-TUG", "Timed Up and Go", TestType.timed_up_and_go, 72),
    }
    code, indication, test_type, age = preset_meta[payload.preset]
    case = PatientCase(
        id=f"case_{uuid.uuid4().hex[:10]}",
        patient_code=payload.patient_code or code,
        age=age, indication=indication, clinician="Demo",
        height_cm=172.0,
    )
    storage.create_case(case)

    video = VideoMetadata(
        id=f"video_{uuid.uuid4().hex[:10]}", case_id=case.id,
        filename=f"{payload.preset}_demo.mp4", stored_path="",
        duration_sec=7.0, fps=30.0, width=1280, height=720, frame_count=210,
        test_type=test_type,
    )
    storage.create_video(video)

    progress = service.create_job(case.id)
    service.submit(progress, case, video, test_type, payload.preset)
    return progress


@router.get("/{analysis_id}/status", response_model=AnalysisProgress)
def get_status(analysis_id: str) -> AnalysisProgress:
    progress = get_storage().get_progress(analysis_id)
    if not progress:
        raise HTTPException(404, "Analysis not found")
    return progress


@router.get("/{analysis_id}/result", response_model=GaitAnalysisResult)
def get_result(analysis_id: str) -> GaitAnalysisResult:
    result = get_storage().get_result(analysis_id)
    if not result:
        progress = get_storage().get_progress(analysis_id)
        if progress and progress.status.value in ("queued", "running"):
            raise HTTPException(409, "Analysis still running")
        raise HTTPException(404, "Result not available")
    return result


@router.get("/{analysis_id}/pose", response_model=PoseTrack)
def get_pose(analysis_id: str) -> PoseTrack:
    pose = get_storage().get_pose(analysis_id)
    if not pose:
        raise HTTPException(404, "Pose track not available")
    return pose


@router.get("/{analysis_id}/keypoints")
def get_keypoints(analysis_id: str):
    """Keypoint time series + per-keypoint tracking-quality stats for the
    Keypoint Analysis view."""
    storage = get_storage()
    pose = storage.get_pose(analysis_id)
    result = storage.get_result(analysis_id)
    if not pose or not result:
        raise HTTPException(404, "Keypoints not available")
    return {
        "analysis_id": analysis_id,
        "analysis_mode": result.analysis_mode,
        "keypoint_source": result.keypoint_source,
        "keypoint_stats": result.keypoint_stats,
        "track": pose,
    }


@router.get("/{analysis_id}/model-status")
def get_analysis_model_status(analysis_id: str):
    """Model provenance for a specific analysis (from the stored result)."""
    result = get_storage().get_result(analysis_id)
    if not result:
        raise HTTPException(404, "Result not available")
    return {
        "analysis_id": analysis_id,
        "analysis_mode": result.analysis_mode,
        "pose_backend": result.pose_backend,
        "simulated_data_used": result.simulated_data_used,
        "model_info": result.model_info,
    }


@router.get("/{analysis_id}/report.json")
def report_json(analysis_id: str):
    result = get_storage().get_result(analysis_id)
    if not result:
        raise HTTPException(404, "Result not available")
    return result


@router.get("/{analysis_id}/report.pdf")
def report_pdf(analysis_id: str):
    storage = get_storage()
    result = storage.get_result(analysis_id)
    if not result:
        raise HTTPException(404, "Result not available")
    case = storage.get_case(result.case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    pdf = build_pdf_report(result, case)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="horalix_report_{analysis_id}.pdf"'
        },
    )


@router.get("/{analysis_id}/overlay-video")
def overlay_video(analysis_id: str):
    settings = get_settings()
    storage = get_storage()
    out = settings.processed_dir / f"{analysis_id}_overlay.mp4"
    if not out.exists():
        result = storage.get_result(analysis_id)
        pose = storage.get_pose(analysis_id)
        if not result or not pose:
            raise HTTPException(404, "Analysis artefacts not available")
        video = storage.get_video(result.video_id)
        src = video.stored_path if video and Path(video.stored_path or "").exists() else None
        try:
            render_overlay_video(pose, result, out, source_video_path=src)
        except Exception as e:  # pragma: no cover - codec/env dependent
            raise HTTPException(500, f"Overlay rendering failed: {e}") from e
    return FileResponse(out, media_type="video/mp4",
                        filename=f"horalix_overlay_{analysis_id}.mp4")
