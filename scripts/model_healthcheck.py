"""Full backend health check across the real-analysis chain.

    python scripts/model_healthcheck.py

Verifies: backend resolves -> model file -> init -> inference -> PoseSequence ->
smoothing -> events -> metrics -> no simulated data in real mode. If a real
walking video exists it additionally requires valid pose frames > 0.

Exit codes: 0 = passed or execution_only; 1 = failed.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401


def main() -> int:
    from app.models.model_loader import get_model_loader

    hc = get_model_loader().healthcheck()
    print("=== Horalix model healthcheck ===")
    print(f"Backend       : {hc.backend}")
    print(f"Analysis mode : {hc.analysis_mode or '-'}")
    print(f"Sample used   : {hc.sample_used}")
    print(f"Valid frames  : {hc.valid_pose_frames}")
    print(f"Simulated data: {'yes' if hc.simulated_data_used else 'no'}")
    print("Checks:")
    for name, ok in hc.checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if hc.error:
        print(f"Error: {hc.error}")
    for d in hc.details:
        print(f"Note: {d}")

    label = {
        "passed": "FULL REAL VERIFIED",
        "execution_only": "MODEL EXECUTION VERIFIED ONLY",
        "failed": "FAILED",
    }.get(hc.status, hc.status.upper())
    print(f"STATUS: {label}")
    return 0 if hc.status in ("passed", "execution_only") else 1


if __name__ == "__main__":
    raise SystemExit(main())
