"""Verify the real pose model imports, initializes and runs inference.

    python scripts/verify_models.py

Exits non-zero if verification fails (so it is CI/healthcheck friendly).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401


def main() -> int:
    from app.models.model_loader import get_model_loader

    loader = get_model_loader()
    status = loader.status()
    res = loader.verify()

    print("=== Horalix model verification ===")
    print(f"Active backend       : {status.active_backend}")
    print(f"Model name           : {res.model_name or '(unresolved)'}")
    print(f"Model version        : {res.model_version or '-'}")
    print(f"Device               : {res.device}")
    print(f"Initialized          : {'yes' if res.initialized else 'no'}")
    print(f"Inference test       : {'passed' if res.inference_ran else 'failed'}")
    print(f"Landmarks returned   : {'yes' if res.landmarks_detected else 'no'} "
          f"({res.landmark_count} keypoints)")
    print(f"Average confidence   : {res.average_confidence:.3f}")
    print(f"Real analysis avail. : {'yes' if status.real_analysis_available else 'no'}")
    if res.error:
        print(f"Error                : {res.error}")
    if res.note:
        print(f"Note                 : {res.note}")
    print(f"RESULT               : {'PASSED' if res.passed else 'FAILED'}")

    if not res.passed:
        print("\nReal pose model is unavailable. Run model setup or switch to Demo Mode:")
        print("  pip install mediapipe")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
