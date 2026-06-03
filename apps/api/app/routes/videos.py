"""Video upload, metadata, raw streaming and pre-analysis quality check."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import get_settings
from app.pipeline.quality import QualityAssessmentService
from app.pipeline.video_processor import VideoError, VideoProcessor, SUPPORTED_SUFFIXES
from app.schemas import (
    CameraView,
    QualityResult,
    TestType,
    VideoMetadata,
)
from app.storage import get_storage

router = APIRouter(prefix="/videos", tags=["videos"])

MAX_BYTES = 400 * 1024 * 1024  # 400 MB upload cap


@router.post("/upload", response_model=VideoMetadata)
async def upload_video(
    case_id: str = Form(...),
    test_type: TestType = Form(TestType.standard_walk),
    camera_view: CameraView = Form(CameraView.unknown),
    calibration_distance_m: float | None = Form(None),
    file: UploadFile = File(...),
) -> VideoMetadata:
    settings = get_settings()
    storage = get_storage()
    if not storage.get_case(case_id):
        raise HTTPException(404, "Case not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            415, f"Unsupported file type '{suffix}'. Allowed: {sorted(SUPPORTED_SUFFIXES)}"
        )

    video_id = f"video_{uuid.uuid4().hex[:10]}"
    dest = settings.uploads_dir / f"{video_id}{suffix}"
    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File too large (max 400 MB).")
            f.write(chunk)

    try:
        meta = VideoProcessor().probe(dest)
    except VideoError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(e)) from e

    video = VideoMetadata(
        id=video_id, case_id=case_id, filename=file.filename or dest.name,
        stored_path=str(dest), duration_sec=round(meta["duration_sec"], 2),
        fps=round(meta["fps"], 2), width=meta["width"], height=meta["height"],
        frame_count=meta["frame_count"], rotation=meta["rotation"],
        test_type=test_type, camera_view=camera_view,
        calibration_available=calibration_distance_m is not None,
        calibration_distance_m=calibration_distance_m,
    )
    return storage.create_video(video)


@router.get("/{video_id}", response_model=VideoMetadata)
def get_video(video_id: str) -> VideoMetadata:
    video = get_storage().get_video(video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    return video


@router.get("/{video_id}/quality", response_model=QualityResult)
def quick_quality(video_id: str) -> QualityResult:
    """Pre-analysis quality check (frame-based: lighting, blur, resolution,
    stability, fps, duration). Full-body & feet visibility are finalised during
    the full analysis once pose is available."""
    storage = get_storage()
    video = storage.get_video(video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    try:
        decoded = VideoProcessor(max_frames=120).load(video.stored_path, min_seconds=0.1)
    except VideoError as e:
        raise HTTPException(400, str(e)) from e
    return QualityAssessmentService().assess(decoded, seq=None)


@router.get("/{video_id}/raw")
def stream_raw(video_id: str):
    video = get_storage().get_video(video_id)
    if not video or not Path(video.stored_path).exists():
        raise HTTPException(404, "Video file not found")
    return FileResponse(video.stored_path, media_type="video/mp4", filename=video.filename)


@router.delete("/{video_id}")
def delete_video(video_id: str):
    """Privacy: delete the stored video file (analysis artefacts are retained)."""
    storage = get_storage()
    video = storage.get_video(video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    Path(video.stored_path).unlink(missing_ok=True)
    return {"deleted": True, "video_id": video_id}
