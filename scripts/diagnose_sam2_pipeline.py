"""Diagnose why SAM2 may or may not be active in real analysis.

    python scripts/diagnose_sam2_pipeline.py [http://127.0.0.1:8010]

Prints the runtime, env, import/checkpoint state, a direct SAM2 inference on the
sample, and (if an API URL is given + reachable) whether a real upload analysis
reports SAM2 active. Ends with SAM2 PIPELINE DIAGNOSED or BLOCKED: <reason>.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
API = sys.argv[1] if len(sys.argv) > 1 else None


def main() -> int:
    print("=== SAM2 pipeline diagnosis ===")
    print(f"python executable        : {sys.executable}")
    print(f"venv                     : {os.environ.get('VIRTUAL_ENV') or sys.prefix}")
    for var in ("HORALIX_ENABLE_SAM2", "HORALIX_SEGMENTATION_BACKEND", "HORALIX_SAM2_MODEL_PATH",
                "HORALIX_REQUIRE_SAM2"):
        print(f"{var:25s}: {os.environ.get(var, '(unset)')}")
    print(f"sam2 importable          : {importlib.util.find_spec('sam2') is not None}")
    print(f"hydra importable         : {importlib.util.find_spec('hydra') is not None}")
    print(f"ultralytics importable   : {importlib.util.find_spec('ultralytics') is not None}")

    from app.config import get_settings
    from app.pipeline.segmentation.sam2_adapter import SAM2Segmenter

    settings = get_settings()
    seg = SAM2Segmenter()
    print(f"enable_sam2 (settings)   : {settings.enable_sam2}")
    print(f"checkpoint path          : {seg.checkpoint} (exists={seg.checkpoint.exists()})")
    print(f"detector path            : {seg.detector_path} (exists={seg.detector_path.exists()})")
    print(f"availability_error       : {seg.availability_error() or 'None (available)'}")

    direct_ok = False
    if SAMPLE.exists() and seg.is_available():
        try:
            from app.pipeline.video_processor import VideoProcessor

            decoded = VideoProcessor(max_frames=12).load(SAMPLE, min_seconds=0.2)
            seg.segment_person(decoded.frames)
            md = seg.status()
            direct_ok = md.get("status") == "WORKING"
            print(f"direct SAM2 inference    : {md.get('status')} "
                  f"(frames={md.get('frames_segmented')}, ms={md.get('processing_time_sec')})")
        except Exception as e:
            print(f"direct SAM2 inference    : FAILED — {type(e).__name__}: {e}")
    else:
        print("direct SAM2 inference    : skipped (sample missing or SAM2 unavailable)")

    # In-pipeline check (runs the orchestrator helper path with SAM2 enabled).
    pipe_status = "skipped"
    if SAMPLE.exists() and seg.is_available():
        try:
            os.environ["HORALIX_ENABLE_SAM2"] = "true"
            get_settings.cache_clear()  # type: ignore[attr-defined]
            from app.pipeline.video_processor import VideoProcessor
            from app.pipeline.orchestrator import _run_optional_helpers
            from app.pipeline.quality import QualityAssessmentService

            decoded = VideoProcessor(max_frames=20).load(SAMPLE, min_seconds=0.2)
            from app.pipeline.pose.mediapipe_adapter import MediaPipeHeavyPoseEstimator
            seq = MediaPipeHeavyPoseEstimator().estimate_2d_pose(decoded.frames, decoded.fps)
            quality = QualityAssessmentService().assess(decoded, seq)
            helpers, _ = _run_optional_helpers(decoded.frames, quality, get_settings(), is_demo=False)
            pipe_status = helpers.get("sam2", {}).get("status")
            print(f"in-pipeline SAM2 status  : {pipe_status} "
                  f"(used_in_analysis={helpers.get('sam2', {}).get('used_in_analysis')})")
            if pipe_status != "WORKING":
                print(f"  reason                 : {helpers.get('sam2', {}).get('error')}")
        except Exception as e:
            print(f"in-pipeline SAM2 status  : ERROR — {type(e).__name__}: {e}")

    if API:
        print(f"api url                  : {API} (use test_real_advanced_analysis.py for HTTP check)")

    print()
    if direct_ok and pipe_status == "WORKING":
        print("SAM2 PIPELINE DIAGNOSED")
        return 0
    if seg.availability_error():
        print(f"BLOCKED: {seg.availability_error()}")
        return 1
    print("BLOCKED: SAM2 available but did not reach WORKING in-pipeline "
          f"(direct_ok={direct_ok}, pipeline={pipe_status}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
