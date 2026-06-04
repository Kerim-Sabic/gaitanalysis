"""Run real Depth Anything V2 relative-depth inference in its isolated runtime."""
from __future__ import annotations

import importlib
import json
import sys
import time

from _vision import classify_error, load_sample_frames, print_result, run_isolated_verifier


def verify():
    delegated = run_isolated_verifier("verify_depth_anything.py", ".venv-depth")
    if delegated is not None:
        return delegated
    result = {
        "model": "Depth Anything V2",
        "weights_present": False,
        "dependencies_installed": False,
        "config_present": False,
        "model_loads": False,
        "inference_runs": False,
        "output_detected": False,
        "integrated_into_pipeline": True,
        "status": "BLOCKED_RUNTIME",
        "error": "",
    }
    try:
        from app.pipeline.depth.depth_anything_adapter import DepthAnythingV2Adapter

        adapter = DepthAnythingV2Adapter()
        result.update({
            "weights_present": adapter.checkpoint.exists(),
            "dependencies_installed": adapter.availability_error() is None,
            "config_present": adapter.source.exists(),
            "checkpoint_path": str(adapter.checkpoint),
            "config_path": str(adapter.source),
            "device": adapter.device,
        })
        frames, _ = load_sample_frames(1)
        started = time.perf_counter()
        depths = adapter.estimate_relative_depth(frames)
        result.update({
            "model_loads": True,
            "inference_runs": True,
            "output_detected": bool(depths.size and float(depths.std()) > 0),
            "status": "WORKING" if depths.size and float(depths.std()) > 0 else "PARTIAL",
            "processing_time_sec": round(time.perf_counter() - started, 4),
            "dependency_versions": {
                "torch": importlib.import_module("torch").__version__,
                "opencv": importlib.import_module("cv2").__version__,
                "depth_anything_v2": "official-source",
            },
            **adapter.last_metadata,
        })
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["status"] = classify_error(result["error"])
    return result


if __name__ == "__main__":
    result = verify()
    if "--json" in sys.argv:
        print(json.dumps(result))
    else:
        print_result(result)
    raise SystemExit(0 if result["status"] == "WORKING" else 1)
