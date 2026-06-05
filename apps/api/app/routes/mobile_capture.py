"""QR phone-capture pairing: desktop creates a session, phone records/uploads.

Desktop polls the session; the phone (via the QR link) connects and uploads a
walking clip, which is fed into the SAME verified real-analysis pipeline as a
normal upload. No accounts, no app install.

State machine: waiting -> phone_connected -> uploading -> analyzing ->
completed | error | expired | cancelled.

Session store is in-memory (fine for a single-worker demo). For multi-worker
production use Redis/DB (see docs/final_deployment_handoff.md).
"""
from __future__ import annotations

import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from typing import Optional

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.pipeline.video_processor import SUPPORTED_SUFFIXES, VideoError, VideoProcessor
from app.schemas import AnalysisOptions, AnalysisStatus, CaptureSource, PatientCase, TestType, VideoMetadata
from app.services.analysis_service import get_analysis_service
from app.storage import get_storage

router = APIRouter(prefix="/mobile", tags=["mobile-capture"])

SESSION_TTL_SECONDS = 15 * 60
MAX_BYTES = 400 * 1024 * 1024

_sessions: dict[str, dict] = {}
_lock = threading.RLock()


class CreateSessionResponse(BaseModel):
    session_id: str
    pairing_token: str
    mobile_url_path: str
    expires_at: str
    status: str


def _err(code: int, ec: str, msg: str, fix: str = "", recoverable: bool = True):
    return HTTPException(code, detail={
        "code": ec, "user_message": msg, "suggested_fix": fix, "recoverable": recoverable,
    })


def _now() -> float:
    return time.time()


def _prune() -> None:
    dead = [sid for sid, s in _sessions.items() if _now() > s["expires"] + 600]
    for sid in dead:
        _sessions.pop(sid, None)


def _resolve(session: dict) -> dict:
    """Reflect analysis progress into the session status + compute time left."""
    if session["status"] == "analyzing" and session.get("analysis_id"):
        prog = get_storage().get_progress(session["analysis_id"])
        if prog:
            if prog.status == AnalysisStatus.completed:
                session["status"] = "completed"
            elif prog.status == AnalysisStatus.failed:
                session["status"] = "error"
                session["error"] = prog.error or "Analysis failed."
    if session["status"] not in ("completed", "error", "cancelled") and _now() > session["expires"]:
        session["status"] = "expired"
    return {
        "session_id": session["id"],
        "status": session["status"],
        "analysis_id": session.get("analysis_id"),
        "error": session.get("error"),
        "expires_at": session["expires_at"],
        "seconds_remaining": max(0, int(session["expires"] - _now())),
        "source_device": "phone_capture",
    }


def _auth(session_id: str, token: str) -> dict:
    with _lock:
        _prune()
        s = _sessions.get(session_id)
        if not s:
            raise _err(404, "session_not_found", "Pairing session not found or already cleared.",
                       "Generate a new QR code on the desktop.")
        if not token or not secrets.compare_digest(token, s["token"]):
            raise _err(403, "invalid_token", "Invalid pairing token.",
                       "Re-scan the QR code from the desktop.")
        if _now() > s["expires"] and s["status"] not in ("completed", "error"):
            s["status"] = "expired"
            raise _err(410, "session_expired", "This pairing session has expired.",
                       "Generate a new QR code on the desktop.")
        return s


# ------------------------------------------------------------------ #
@router.post("/session", response_model=CreateSessionResponse)
def create_session(options: Optional[AnalysisOptions] = Body(default=None)) -> CreateSessionResponse:
    """Create a pairing session. The desktop may pass the chosen analysis setup
    (``options``) so the phone-captured clip inherits the same model selection."""
    session_id = "sess_" + secrets.token_urlsafe(16)
    token = secrets.token_urlsafe(24)
    expires = _now() + SESSION_TTL_SECONDS
    expires_at = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
    if options is not None:
        options.capture_source = CaptureSource.phone
    with _lock:
        _prune()
        _sessions[session_id] = {
            "id": session_id, "token": token, "status": "waiting",
            "created": _now(), "expires": expires, "expires_at": expires_at,
            "analysis_id": None, "case_id": None, "error": None,
            "options": options,
        }
    return CreateSessionResponse(
        session_id=session_id, pairing_token=token,
        mobile_url_path=f"/mobile-capture/{session_id}?token={token}",
        expires_at=expires_at, status="waiting",
    )


@router.get("/session/{session_id}")
def get_session(session_id: str, token: str):
    s = _auth(session_id, token)
    with _lock:
        return _resolve(s)


@router.post("/session/{session_id}/connect")
def connect_session(session_id: str, token: str):
    s = _auth(session_id, token)
    with _lock:
        if s["status"] == "waiting":
            s["status"] = "phone_connected"
        return _resolve(s)


@router.post("/session/{session_id}/cancel")
def cancel_session(session_id: str, token: str):
    s = _auth(session_id, token)
    with _lock:
        if s["status"] not in ("completed", "error"):
            s["status"] = "cancelled"
        return _resolve(s)


@router.post("/session/{session_id}/upload")
async def upload_from_phone(session_id: str, token: str,
                            file: UploadFile = File(...),
                            test_type: TestType = TestType.standard_walk):
    s = _auth(session_id, token)
    if s["status"] in ("analyzing", "completed"):
        raise _err(409, "already_uploaded", "This session already has an upload.",
                   "Generate a new QR code to record again.")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise _err(415, "unsupported_video_format",
                   f"Unsupported video type '{suffix or '?'}'.",
                   "Record with the in-app camera or choose an MP4/WebM/MOV clip.")

    settings = get_settings()
    storage = get_storage()
    with _lock:
        s["status"] = "uploading"

    video_id = f"video_{uuid.uuid4().hex[:10]}"
    dest = settings.uploads_dir / f"{video_id}{suffix}"
    size = 0
    try:
        with dest.open("wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    with _lock:
                        s["status"] = "phone_connected"
                    raise _err(413, "upload_too_large", "Video is larger than 400 MB.",
                               "Record a shorter clip (5–15 s).")
                fh.write(chunk)
        meta = VideoProcessor().probe(dest)
    except VideoError as e:
        dest.unlink(missing_ok=True)
        with _lock:
            s["status"] = "error"
            s["error"] = str(e)
        raise _err(400, "video_decode_failed", f"Could not read the video. {e}",
                   "Re-record with the in-app camera.") from e

    # Inherit the desktop-chosen setup (model selection + protocol + calibration).
    options: Optional[AnalysisOptions] = s.get("options")
    if options is not None:
        if options.protocol:
            test_type = options.protocol
        options.capture_source = CaptureSource.phone

    case = PatientCase(
        id=f"case_{uuid.uuid4().hex[:10]}",
        patient_code=f"PHONE-{secrets.token_hex(2).upper()}",
        indication="Phone capture", clinician="Phone capture",
        height_cm=(options.patient_height_cm if options else None),
    )
    storage.create_case(case)
    video = VideoMetadata(
        id=video_id, case_id=case.id, filename=file.filename or dest.name,
        stored_path=str(dest), duration_sec=round(meta["duration_sec"], 2),
        fps=round(meta["fps"], 2), width=meta["width"], height=meta["height"],
        frame_count=meta["frame_count"], rotation=meta["rotation"], test_type=test_type,
    )
    storage.create_video(video)

    service = get_analysis_service()
    progress = service.create_job(case.id)
    # Real analysis, never demo; inherits the desktop setup options.
    service.submit(progress, case, video, test_type, None, options=options)
    with _lock:
        s["status"] = "analyzing"
        s["analysis_id"] = progress.analysis_id
        s["case_id"] = case.id
        return {"ok": True, "status": "analyzing", "analysis_id": progress.analysis_id,
                "source_device": "phone_capture"}
