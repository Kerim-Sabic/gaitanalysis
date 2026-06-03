"""Model inventory: what weights exist, what runtimes are installed, which
adapters are implemented, which backends are verified vs placeholder.

    python scripts/model_inventory.py
"""
from __future__ import annotations

import importlib.util

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT


def _have(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


def _mb(p):
    return f"{p.stat().st_size / 1e6:.2f} MB" if p.exists() else "missing"


def main() -> int:
    print("=== Horalix model inventory ===\n")

    print("[Weights present]")
    weights = {
        "mediapipe pose_landmarker_full.task": REPO_ROOT / "models/pose/mediapipe/pose_landmarker_full.task",
        "mediapipe pose_landmarker_lite.task": REPO_ROOT / "models/pose/mediapipe/pose_landmarker_lite.task",
        "mediapipe pose_landmarker_heavy.task": REPO_ROOT / "models/pose/mediapipe/pose_landmarker_heavy.task",
        "ultralytics yolov8n-pose.pt": REPO_ROOT / "models/pose/ultralytics/yolov8n-pose.pt",
    }
    for label, p in weights.items():
        print(f"  {'OK ' if p.exists() else '-- '} {label}: {_mb(p)}")

    print("\n[Runtimes installed]")
    for mod in ("mediapipe", "mediapipe.tasks.python.vision", "ultralytics", "cv2",
                "numpy", "scipy", "reportlab", "torch", "mmpose"):
        print(f"  {'OK ' if _have(mod) else '-- '} {mod}")

    print("\n[Backends]")
    from app.models import model_registry as reg

    for name, spec in reg.REGISTRY.items():
        avail = spec.adapter.is_available() if spec.kind == "real" else True
        err = spec.availability_error() if spec.kind == "real" and not avail else ""
        kind = spec.kind
        feet = "heel/foot_index" if getattr(spec, "feet_keypoints", False) else "COCO-17 only"
        print(f"  {name:18s} kind={kind:5s} available={'yes' if avail else 'no':3s} "
              f"({feet}){(' — ' + err) if err else ''}")

    print("\n[Real analysis availability]")
    from app.models.model_loader import get_model_loader

    st = get_model_loader().status()
    print(f"  configured_backend           : {st.configured_backend}")
    print(f"  configured_backend_available : {st.configured_backend_available}")
    print(f"  any_real_backend_available   : {st.any_real_backend_available}")
    print(f"  available_real_backends      : {reg.available_real_backends()}")
    print(f"  model_file                   : {st.model_file or '-'}")

    print("\n[Placeholders / not wired]  mmpose, sam2, depth_anything, wham (weights present, "
          "runtimes/adapters not part of MVP).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
