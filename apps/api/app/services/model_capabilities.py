"""Model control-plane: capabilities discovery, per-request plan resolution, preflight.

The frontend pre-analysis setup renders model cards and the preflight plan from
these helpers — it must NOT hardcode model status. Status strings are computed
live from the same adapters the pipeline uses, so a card never claims a model is
ready when the runtime cannot load it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.config import Settings, get_settings
from app.models import model_registry as registry
from app.pipeline.orchestrator import _helper_blocked_status
from app.schemas import (
    AnalysisOptions,
    AnalysisQualityMode,
    CalibrationMode,
    ModelCapabilities,
    ModelCapability,
    PreflightRequest,
    PreflightResponse,
)

# --------------------------------------------------------------------------- #
# Static, human-facing metadata per model (status is merged in live).
# --------------------------------------------------------------------------- #
_POSE_META: dict[str, dict] = {
    "auto_best": {
        "name": "Automatic (best available)",
        "what_it_does": "Picks the best available real pose backend for this clip. "
        "In fast mode it runs the single preferred backend; in full mode it "
        "compares all and selects the highest-scoring output.",
        "limitations": [
            "Selection is measured per clip; the chosen backend can vary by video.",
        ],
        "recommended": True,
    },
    "mediapipe_tasks_heavy": {
        "name": "MediaPipe Pose (Heavy)",
        "what_it_does": "Highest-accuracy MediaPipe landmark model with heel and "
        "foot-index keypoints — best for gait/foot events.",
        "limitations": ["CPU inference is slower than the Full model."],
    },
    "mediapipe_tasks_full": {
        "name": "MediaPipe Pose (Full)",
        "what_it_does": "Balanced MediaPipe landmark model with feet keypoints; "
        "good speed/accuracy trade-off for most clips.",
        "limitations": ["Slightly lower accuracy than Heavy on hard poses."],
    },
    "ultralytics_pose": {
        "name": "Ultralytics YOLOv8-Pose",
        "what_it_does": "Fast COCO-17 whole-body keypoint detector used as a "
        "robust fallback and as the SAM2 box prompt.",
        "limitations": [
            "COCO-17 only: no dedicated heel/foot-index keypoints, so foot "
            "events are approximated from the ankle.",
        ],
    },
    "mmpose_rtmw": {
        "name": "MMPose RTMW (whole-body)",
        "what_it_does": "High-accuracy whole-body pose with rich foot keypoints.",
        "limitations": ["Requires the Docker runtime (compiled mmcv ops)."],
    },
    "mmpose_rtmw3d": {
        "name": "MMPose RTMW3D",
        "what_it_does": "Experimental 3D whole-body pose.",
        "limitations": ["Needs a matching config + verified 3D mapping."],
    },
}

_HELPER_META: dict[str, dict] = {
    "sam2": {
        "name": "SAM2.1 segmentation",
        "what_it_does": "Segments the walking subject to validate capture quality "
        "(full-body + feet-region visibility) using a pose box prompt.",
        "limitations": [
            "Capture-quality helper only — masks are sampled, not propagated to "
            "every frame, and do not change gait metrics directly.",
        ],
        "fix_hint": "pip install -r apps/api/requirements-sam2.txt and place the "
        "SAM2.1 checkpoint under models/segmentation/.",
    },
    "depth": {
        "name": "Depth Anything V2",
        "what_it_does": "Estimates relative monocular depth to add scene context.",
        "limitations": [
            "Relative depth only — NOT calibrated clinical distance.",
        ],
        "fix_hint": "pip install -r apps/api/requirements-depth.txt (torch + "
        "transformers) and configure HORALIX_DEPTH_MODEL_PATH if needed.",
    },
    "wham": {
        "name": "WHAM 3D reconstruction",
        "what_it_does": "Optional 3D body reconstruction from monocular video.",
        "limitations": ["Single-camera 2D analysis runs without it."],
        "fix_hint": "Provide the licensed SMPL_NEUTRAL.pkl from "
        "https://smpl.is.tue.mpg.de under models/body_models/smpl/ (never auto-downloaded).",
    },
}


# --------------------------------------------------------------------------- #
# Plan resolution (shared by orchestrator + preflight)
# --------------------------------------------------------------------------- #
@dataclass
class ResolvedPlan:
    quality_mode: AnalysisQualityMode
    pose_backend: str  # canonical backend the user asked for (may be auto_best)
    auto_best_mode: str
    enable_sam2: bool
    enable_depth: bool
    enable_wham: bool
    require_sam2: bool
    require_depth: bool
    require_pose_backend: bool
    explicit_pose_backend: bool  # user pinned a concrete (non-auto) backend
    notes: list[str] = field(default_factory=list)


def resolve_analysis_plan(
    options: Optional[AnalysisOptions], settings: Optional[Settings] = None
) -> ResolvedPlan:
    settings = settings or get_settings()
    opts = options or AnalysisOptions()
    mode = opts.analysis_quality_mode

    # Pose backend: explicit option wins, else server default.
    raw_backend = opts.pose_backend or settings.pose_backend or "auto_best"
    pose_backend = registry.canonical(raw_backend)
    explicit_pose_backend = bool(opts.pose_backend) and pose_backend != "auto_best"
    auto_best_mode = (opts.auto_best_mode or settings.auto_best_mode or "fast").lower()

    # Helper defaults per mode; explicit option always wins.
    # Advanced Clinical turns SAM2 + Depth ON when available; Standard/Expert
    # fall back to the server-configured defaults unless overridden.
    if mode == AnalysisQualityMode.advanced_clinical:
        sam2_default, depth_default = True, True
    else:
        sam2_default, depth_default = settings.enable_sam2, settings.enable_depth

    enable_sam2 = opts.enable_sam2 if opts.enable_sam2 is not None else sam2_default
    enable_depth = opts.enable_depth if opts.enable_depth is not None else depth_default
    enable_wham = opts.enable_wham if opts.enable_wham is not None else settings.enable_wham

    require_advanced = bool(opts.require_advanced_helpers)
    require_sam2 = settings.require_sam2 or (require_advanced and enable_sam2)
    require_depth = settings.require_depth or (require_advanced and enable_depth)

    return ResolvedPlan(
        quality_mode=mode,
        pose_backend=pose_backend,
        auto_best_mode=auto_best_mode,
        enable_sam2=bool(enable_sam2),
        enable_depth=bool(enable_depth),
        enable_wham=bool(enable_wham),
        require_sam2=bool(require_sam2),
        require_depth=bool(require_depth),
        require_pose_backend=bool(opts.require_selected_pose_backend),
        explicit_pose_backend=explicit_pose_backend,
    )


# --------------------------------------------------------------------------- #
# Live status helpers
# --------------------------------------------------------------------------- #
def _pose_status(name: str) -> tuple[str, bool, str]:
    """Return (status, available, fix_hint) for a real pose backend."""
    spec = registry.REGISTRY.get(name)
    if spec is None:
        return "UNKNOWN", False, ""
    if name == "auto_best":
        available = bool(registry.available_real_backends())
        if available:
            return "READY", True, ""
        err = spec.availability_error() or "No real pose backend is installed."
        return _helper_blocked_status(err), False, err
    available = spec.adapter.is_available()
    if available:
        return "READY", True, ""
    err = spec.availability_error() or "Backend unavailable."
    return _helper_blocked_status(err), False, err


def _sam2_live() -> tuple[str, bool, str]:
    from app.pipeline.segmentation.sam2_adapter import SAM2Segmenter

    seg = SAM2Segmenter()
    if seg.is_available():
        return "AVAILABLE", True, ""
    err = seg.availability_error() or "SAM2 unavailable."
    return _helper_blocked_status(err), False, err


def _depth_live() -> tuple[str, bool, str]:
    from app.pipeline.depth.depth_anything_adapter import DepthAnythingV2Adapter

    dep = DepthAnythingV2Adapter()
    if dep.is_available():
        return "AVAILABLE", True, ""
    err = dep.availability_error() or "Depth Anything V2 unavailable."
    return _helper_blocked_status(err), False, err


def _wham_live() -> tuple[str, bool, str]:
    try:
        from app.pipeline.pose.wham_adapter import WHAMAdapter

        info = WHAMAdapter.status()
        status = str(info.get("status", "BLOCKED_RUNTIME"))
        return status, status == "WORKING", str(info.get("error", "") or "")
    except Exception as exc:  # pragma: no cover - defensive
        return "BLOCKED_RUNTIME", False, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# Capabilities
# --------------------------------------------------------------------------- #
def build_capabilities(settings: Optional[Settings] = None) -> ModelCapabilities:
    settings = settings or get_settings()
    default_backend = registry.canonical(settings.pose_backend or "auto_best")

    pose_backends: list[ModelCapability] = []
    for name in ("auto_best", "mediapipe_tasks_heavy", "mediapipe_tasks_full",
                 "ultralytics_pose", "mmpose_rtmw", "mmpose_rtmw3d"):
        spec = registry.REGISTRY.get(name)
        meta = _POSE_META.get(name, {})
        status, available, err = _pose_status(name)
        pose_backends.append(ModelCapability(
            id=name,
            name=meta.get("name", name),
            category="pose_backend",
            kind="real",
            status=status,
            available=available,
            selected_by_default=name == default_backend,
            recommended=bool(meta.get("recommended", False)),
            feet_keypoints=bool(getattr(spec, "feet_keypoints", False)),
            what_it_does=meta.get("what_it_does", ""),
            limitations=list(meta.get("limitations", [])),
            fix_hint=err or meta.get("fix_hint", ""),
            requires_docker=status == "DOCKER_REQUIRED",
            requires_license=status == "BLOCKED_LICENSED_ASSETS",
        ))

    helpers: list[ModelCapability] = []
    for hid, live in (("sam2", _sam2_live), ("depth", _depth_live), ("wham", _wham_live)):
        meta = _HELPER_META[hid]
        status, available, err = live()
        helpers.append(ModelCapability(
            id=hid,
            name=meta["name"],
            category="helper",
            kind="helper",
            status=status,
            available=available,
            what_it_does=meta["what_it_does"],
            limitations=list(meta["limitations"]),
            fix_hint=err or meta.get("fix_hint", ""),
            requires_docker=status == "DOCKER_REQUIRED",
            requires_license=status == "BLOCKED_LICENSED_ASSETS",
        ))

    quality_modes = [
        {
            "id": AnalysisQualityMode.standard.value,
            "name": "Standard",
            "summary": "Fast real pose analysis only — no advanced helpers.",
            "best_for": "Quick screening and most clinic clips.",
            "enables_helpers": False,
        },
        {
            "id": AnalysisQualityMode.advanced_clinical.value,
            "name": "Advanced Clinical",
            "summary": "Adds SAM2 segmentation + Depth helpers when installed.",
            "best_for": "Richer capture-quality evidence on a capable machine.",
            "enables_helpers": True,
        },
        {
            "id": AnalysisQualityMode.expert.value,
            "name": "Expert",
            "summary": "Manual backend + helper selection and strict requirements.",
            "best_for": "Research / benchmarking with full control.",
            "enables_helpers": True,
        },
    ]

    return ModelCapabilities(
        real_analysis_available=bool(registry.available_real_backends()),
        default_pose_backend=default_backend,
        auto_best_mode=(settings.auto_best_mode or "fast").lower(),
        pose_backends=pose_backends,
        helpers=helpers,
        quality_modes=quality_modes,
        notes=[
            "Status is computed live from the runtime — a card is READY only if "
            "the model can actually load on this server.",
            "Advanced helpers add capture-quality context; they do not constitute "
            "clinical validation or a diagnosis.",
        ],
    )


# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #
def build_preflight(req: PreflightRequest, settings: Optional[Settings] = None) -> PreflightResponse:
    settings = settings or get_settings()
    plan = resolve_analysis_plan(req, settings)

    pose_status, pose_available, pose_err = _pose_status(plan.pose_backend)
    sam2_status, sam2_available, sam2_err = _sam2_live()
    depth_status, depth_available, depth_err = _depth_live()

    blocked: list[str] = []
    warnings: list[str] = []
    will_run: list[str] = []

    # Pose backend is the hard requirement for real analysis.
    if not pose_available:
        msg = f"Pose backend '{plan.pose_backend}' is not ready: {pose_err}"
        if plan.require_pose_backend or plan.explicit_pose_backend:
            blocked.append(msg)
        else:
            warnings.append(msg + " — analysis cannot run without a real backend.")
            blocked.append("No real pose backend is available.")
    else:
        will_run.append(f"Pose: {plan.pose_backend}"
                        + (f" ({plan.auto_best_mode})" if plan.pose_backend == "auto_best" else ""))

    # SAM2
    sam2_expected = "NOT_REQUESTED"
    if plan.enable_sam2:
        if sam2_available:
            sam2_expected = "WILL_RUN"
            will_run.append("SAM2 segmentation (capture quality)")
        else:
            sam2_expected = sam2_status
            if plan.require_sam2:
                blocked.append(f"SAM2 was required but is not active: {sam2_err}")
            else:
                warnings.append(f"SAM2 requested but unavailable — will be skipped: {sam2_err}")

    # Depth
    depth_expected = "NOT_REQUESTED"
    if plan.enable_depth:
        if depth_available:
            depth_expected = "WILL_RUN"
            will_run.append("Depth Anything V2 (relative depth)")
        else:
            depth_expected = depth_status
            if plan.require_depth:
                blocked.append(f"Depth was required but is not active: {depth_err}")
            else:
                warnings.append(f"Depth requested but unavailable — will be skipped: {depth_err}")

    # Calibration sanity.
    if req.calibration_mode == CalibrationMode.patient_height and not req.patient_height_cm:
        warnings.append("Patient-height calibration selected but no height provided.")
    if req.calibration_mode == CalibrationMode.known_distance and not req.known_distance_m:
        warnings.append("Known-distance calibration selected but no distance provided.")

    # Runtime estimate (rough, CPU): pose dominates; helpers add fixed cost.
    est = 7.0 if plan.auto_best_mode == "fast" else 14.0
    if plan.enable_sam2 and sam2_available:
        est += 3.0
    if plan.enable_depth and depth_available:
        est += 2.5

    return PreflightResponse(
        can_start=not blocked,
        analysis_quality_mode=plan.quality_mode,
        pose_backend=plan.pose_backend,
        auto_best_mode=plan.auto_best_mode,
        will_run=will_run,
        blocked_reasons=blocked,
        warnings=warnings,
        estimated_runtime_sec=round(est, 1),
        expected_transparency={
            "quality_mode": plan.quality_mode.value,
            "pose_backend_requested": plan.pose_backend,
            "pose_backend_status": pose_status,
            "sam2_requested": plan.enable_sam2,
            "sam2_expected_status": sam2_expected,
            "depth_requested": plan.enable_depth,
            "depth_expected_status": depth_expected,
            "calibration_mode": req.calibration_mode.value,
        },
        requires={
            "pose_backend": plan.require_pose_backend or plan.explicit_pose_backend,
            "sam2": plan.require_sam2,
            "depth": plan.require_depth,
        },
    )
