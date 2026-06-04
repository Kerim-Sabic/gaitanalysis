"""Report optional Depth Anything V2 runtime status."""
from __future__ import annotations

from _vision import REPO_ROOT, have_module, print_result


def verify():
    weight = REPO_ROOT / "models/depth/Depth-Anything-V2-Large/depth_anything_v2_vitl.pth"
    dependency = have_module("depth_anything_v2")
    error = ""
    status = "NOT_REQUIRED"
    if not weight.exists():
        status, error = "MISSING_WEIGHT", f"Missing {weight}"
    elif not dependency:
        status, error = "MISSING_DEPENDENCY", "Depth Anything V2 runtime package/source is not installed."
    else:
        status, error = "BLOCKED", "Depth runtime exists but inference is not yet verified."
    return {
        "model": "Depth Anything V2",
        "weights_present": weight.exists(),
        "dependencies_installed": dependency,
        "config_present": dependency,
        "model_loads": False,
        "inference_runs": False,
        "output_detected": False,
        "integrated_into_pipeline": False,
        "status": status,
        "error": error,
    }


if __name__ == "__main__":
    result = verify()
    print_result(result)
    raise SystemExit(0 if result["status"] == "WORKING" else 1)
