"""Run real SAM2.1 Tiny inference in the isolated SAM2 runtime."""
from __future__ import annotations

import importlib
import json
import sys
import time

from _vision import (
    classify_error,
    load_sample_frames,
    print_result,
    run_isolated_verifier,
)


def verify():
    delegated = run_isolated_verifier("verify_sam2.py", ".venv-sam2")
    if delegated is not None:
        return delegated
    result = {
        "model": "SAM2.1 Tiny",
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
        from app.pipeline.segmentation.sam2_adapter import SAM2Segmenter

        segmenter = SAM2Segmenter()
        result.update({
            "weights_present": segmenter.checkpoint.exists() and segmenter.detector_path.exists(),
            "dependencies_installed": segmenter.availability_error() is None,
            "config_present": bool(segmenter.config),
            "checkpoint_path": str(segmenter.checkpoint),
            "config_path": segmenter.config,
            "detector_path": str(segmenter.detector_path),
            "device": segmenter.device,
        })
        frames, _ = load_sample_frames(3)
        started = time.perf_counter()
        masks = segmenter.segment_person(frames)
        result.update({
            "model_loads": True,
            "inference_runs": True,
            "output_detected": bool(masks is not None and masks.any()),
            "status": "WORKING" if masks is not None and masks.any() else "PARTIAL",
            "processing_time_sec": round(time.perf_counter() - started, 4),
            "dependency_versions": {
                "torch": importlib.import_module("torch").__version__,
                "ultralytics": importlib.import_module("ultralytics").__version__,
                "sam2": "official-source",
            },
            **segmenter.last_metadata,
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
