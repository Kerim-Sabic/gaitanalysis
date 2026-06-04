"""Near-real-time live preview endpoints.

``POST /live/frame`` runs single-frame pose for capture guidance. This is a
PREVIEW path — the recorded clip is uploaded and analysed by the verified
backend for the actual report. Never returns simulated data; fails clearly if
the live model is unavailable (HTTP 503).
"""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.pipeline.pose.live_pose import LivePoseUnavailable, get_live_pose_service

router = APIRouter(prefix="/live", tags=["live"])

MAX_FRAME_BYTES = 8 * 1024 * 1024  # 8 MB per preview frame


@router.get("/status")
def live_status():
    svc = get_live_pose_service()
    s = svc.status()
    s["final_backend"] = get_settings().final_backend
    return s


@router.post("/frame")
async def live_frame(frame_index: int = 0, file: UploadFile = File(...)):
    svc = get_live_pose_service()
    if not svc.is_available():
        raise HTTPException(
            503,
            detail={
                "code": "live_model_unavailable",
                "user_message": "Live preview model is unavailable.",
                "technical_detail": svc.available_error(),
                "suggested_fix": "Install MediaPipe and the .task model, or use upload analysis.",
                "recoverable": True,
            },
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(400, detail={"code": "empty_frame", "user_message": "Empty frame."})
    if len(raw) > MAX_FRAME_BYTES:
        raise HTTPException(413, detail={"code": "frame_too_large", "user_message": "Frame too large."})

    import cv2

    arr = np.frombuffer(raw, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(
            400,
            detail={"code": "frame_decode_failed",
                    "user_message": "Could not decode the camera frame.",
                    "suggested_fix": "Send a JPEG/PNG frame.", "recoverable": True},
        )
    try:
        return svc.infer_frame(bgr, frame_index=frame_index)
    except LivePoseUnavailable as e:
        raise HTTPException(503, detail={"code": "live_model_unavailable",
                                         "user_message": "Live preview model is unavailable.",
                                         "technical_detail": str(e), "recoverable": True}) from e
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(500, detail={"code": "inference_failed",
                                         "user_message": "Live inference failed.",
                                         "technical_detail": str(e), "recoverable": True}) from e
