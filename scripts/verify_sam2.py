"""Report SAM2.1 Tiny weight/runtime/integration status without fake inference."""
from __future__ import annotations

from _vision import REPO_ROOT, have_module, print_result


def verify():
    weight = REPO_ROOT / "models/segmentation/sam2.1_hiera_tiny.pt"
    dependency = have_module("sam2")
    error = ""
    status = "BLOCKED"
    if not weight.exists():
        status, error = "MISSING_WEIGHT", f"Missing {weight}"
    elif not dependency:
        status, error = "MISSING_DEPENDENCY", "Official SAM2 package is not installed."
    else:
        error = "SAM2 package and weight exist, but prompted video-mask inference is not verified."
    return {
        "model": "SAM2.1 Tiny",
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
