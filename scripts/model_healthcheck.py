"""Full backend health check across the real-analysis chain.

    python scripts/model_healthcheck.py

Verifies: backend resolves -> model initializes -> inference runs ->
PoseSequence valid -> metrics pipeline accepts output -> no simulated data in
real mode. Exits non-zero unless ALL checks pass (no fake "healthy" states).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401


def main() -> int:
    from app.models.model_loader import get_model_loader

    hc = get_model_loader().healthcheck()
    print("=== Horalix model healthcheck ===")
    print(f"Backend       : {hc.backend}")
    print(f"Analysis mode : {hc.analysis_mode or '-'}")
    print(f"Simulated data: {'yes' if hc.simulated_data_used else 'no'}")
    print("Checks:")
    for name, ok in hc.checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if hc.error:
        print(f"Error: {hc.error}")
    print(f"RESULT: {'PASSED' if hc.passed else 'FAILED'}")
    return 0 if hc.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
