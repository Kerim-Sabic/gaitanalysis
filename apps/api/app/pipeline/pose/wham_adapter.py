"""WHAM monocular 3D body-reconstruction adapter — honest, never faked.

WHAM is only enabled when ALL legal assets and the runtime exist:
  * torch + the WHAM runtime,
  * a WHAM checkpoint under models/pose/wham/checkpoints/,
  * **licensed** SMPL body models (SMPL_NEUTRAL.pkl, optionally male/female)
    under models/body_models/smpl/ — these must be obtained from the official
    licensed source (https://smpl.is.tue.mpg.de) and are NOT downloaded here.

Until then it reports a precise blocked status; it never produces 3D output.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.config import REPO_ROOT

CHECKPOINT_DIR = REPO_ROOT / "models" / "pose" / "wham" / "checkpoints"
SMPL_DIRS = [
    REPO_ROOT / "models" / "body_models" / "smpl",
    REPO_ROOT / "models" / "pose" / "wham" / "smpl",
]
SMPL_FILES = ["SMPL_NEUTRAL.pkl", "basicModel_neutral_lbs_10_207_0_v1.0.0.pkl"]


def _have(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


def _checkpoint() -> Path | None:
    if not CHECKPOINT_DIR.exists():
        return None
    for p in CHECKPOINT_DIR.glob("*.pth*"):
        return p
    return None


def _smpl_present() -> bool:
    for d in SMPL_DIRS:
        if d.exists() and any((d / f).exists() for f in SMPL_FILES):
            return True
        if d.exists() and any(d.glob("*.pkl")):
            return True
    return False


class WHAMAdapter:
    """Status-only adapter. ``estimate_*`` raise until WHAM is truly enabled."""

    backend_id = "wham"

    @staticmethod
    def dependencies_installed() -> bool:
        return _have("torch") and _have("wham") and _have("smplx")

    @classmethod
    def status(cls) -> dict:
        deps = cls.dependencies_installed()
        ckpt = _checkpoint()
        smpl = _smpl_present()
        if not smpl:
            status = "BLOCKED_LICENSED_ASSETS"
            blocker = ("Licensed SMPL body model not found (SMPL_NEUTRAL.pkl). "
                       "Obtain it from https://smpl.is.tue.mpg.de (licensed) and place "
                       "it under models/body_models/smpl/.")
        elif not deps:
            status = "BLOCKED_DEPENDENCY"
            blocker = "Missing runtime: torch + wham + smplx are not installed."
        elif ckpt is None:
            status = "BLOCKED_WEIGHT"
            blocker = "WHAM checkpoint not found under models/pose/wham/checkpoints/."
        else:
            # Even with assets present we do not claim WORKING without a verified
            # inference path; report PARTIAL so it is never silently trusted.
            status = "PARTIAL"
            blocker = ("Assets present but verified WHAM inference + 3D PoseSequence "
                       "mapping is not enabled in this build.")
        return {
            "model": "WHAM",
            "dependencies_installed": deps,
            "checkpoint_present": ckpt is not None,
            "checkpoint_path": str(ckpt) if ckpt else "",
            "smpl_assets_present": smpl,
            "config_present": deps,
            "model_loads": False,
            "inference_runs": False,
            "output_detected": False,
            "integrated_into_pipeline": False,
            "status": status,
            "error": blocker,
        }

    @staticmethod
    def is_available() -> bool:
        return False  # never selectable as a pose backend in this build

    def estimate_2d_pose(self, frames, fps):  # pragma: no cover - guarded
        raise RuntimeError(
            "WHAM 3D reconstruction is not enabled. " + WHAMAdapter.status()["error"]
        )
