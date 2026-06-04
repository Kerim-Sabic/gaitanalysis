"""End-to-end HTTP assertion for transparent real multi-model selection."""
from __future__ import annotations

import sys

import _bootstrap  # noqa: F401
from test_real_upload_flow import BASE as DEFAULT_BASE
from test_real_upload_flow import _get, main as run_real_flow

BASE = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE


def main() -> int:
    # Reuse the strict real upload/export assertions first.
    code = run_real_flow()
    if code:
        return code
    model_status = _get("/models/status")
    checks = {
        "auto_best configured": model_status.get("configured_backend") == "auto_best",
        "multiple real backends available": sum(
            bool(value) for name, value in model_status.get("backend_availability", {}).items()
            if name != "auto_best"
        ) >= 2,
        "demo not an auto candidate": "demo" not in model_status.get("backend_availability", {}),
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    ok = all(checks.values())
    print("STATUS:", "MULTI-MODEL HTTP VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
