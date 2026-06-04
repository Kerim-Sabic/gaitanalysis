"""Profile each stage of the gait pipeline on the real sample video.

    python scripts/profile_gait_pipeline.py

Writes data/processed/performance/profile_report.{md,json} (git-ignored) and
prints a per-stage timing table. Used to decide where optimization (and whether
Rust) is justified.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager

import numpy as np

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
OUT = REPO_ROOT / "data" / "processed" / "performance"


@contextmanager
def timed(store: dict, key: str):
    t = time.perf_counter()
    try:
        yield
    finally:
        store[key] = round((time.perf_counter() - t) * 1000.0, 1)  # ms


def main() -> int:
    if not SAMPLE.exists():
        print(f"Sample video missing at {SAMPLE}; cannot profile. STATUS: SAMPLE MISSING")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)

    from app.pipeline.events import GaitEventDetector
    from app.pipeline.keypoint_quality import compute_keypoint_stats
    from app.pipeline.metrics import GaitMetricsCalculator
    from app.pipeline.pose.mediapipe_adapter import (
        MediaPipeFullPoseEstimator,
        MediaPipeHeavyPoseEstimator,
    )
    from app.pipeline.quality import QualityAssessmentService
    from app.pipeline.smoothing import TemporalSmoothingService

    timings: dict[str, float] = {}
    meta: dict = {"sample": str(SAMPLE)}

    # --- Decode ---
    from app.pipeline.video_processor import VideoProcessor

    with timed(timings, "decode_ms"):
        decoded = VideoProcessor().load(SAMPLE, min_seconds=0.5)
    meta["frames"] = int(decoded.frames.shape[0])
    meta["fps"] = round(decoded.fps, 2)

    # --- Per-backend inference ---
    backends = [("mediapipe_full", MediaPipeFullPoseEstimator),
                ("mediapipe_heavy", MediaPipeHeavyPoseEstimator)]
    try:
        from app.pipeline.pose.ultralytics_adapter import UltralyticsPoseEstimator
        if UltralyticsPoseEstimator.is_available():
            backends.append(("ultralytics_pose", UltralyticsPoseEstimator))
    except Exception:
        pass

    seqs = {}
    for name, adapter in backends:
        if not adapter.is_available():
            timings[f"infer_{name}_ms"] = -1.0
            continue
        try:
            est = adapter()
            with timed(timings, f"infer_{name}_ms"):
                seqs[name] = est.estimate_2d_pose(decoded.frames, decoded.fps)
        except Exception as e:
            timings[f"infer_{name}_ms"] = -1.0
            meta[f"{name}_error"] = f"{type(e).__name__}: {e}"

    # Choose heavy (preferred) for downstream stage timing.
    seq = seqs.get("mediapipe_heavy") or next(iter(seqs.values()), None)
    if seq is None:
        print("No backend produced a sequence; cannot profile post-processing.")
        return 1

    smoother = TemporalSmoothingService()
    with timed(timings, "smoothing_ms"):
        smoothed = smoother.smooth(seq)
    with timed(timings, "quality_ms"):
        quality = QualityAssessmentService().assess(decoded, smoothed)
    with timed(timings, "keypoint_quality_ms"):
        compute_keypoint_stats(smoothed)
    with timed(timings, "gait_events_ms"):
        events = GaitEventDetector().detect(smoothed)
    with timed(timings, "metrics_ms"):
        GaitMetricsCalculator().compute(smoothed, events, quality)

    # --- End-to-end run + export (decode happens again inside run) ---
    import uuid

    from app.pipeline.orchestrator import GaitPipeline
    from app.reporting import build_pdf_report
    from app.schemas import PatientCase, TestType, VideoMetadata

    case = PatientCase(id="prof", patient_code="PROF", age=40, height_cm=172)
    video = VideoMetadata(id="profvid", case_id="prof", filename=SAMPLE.name,
                          stored_path=str(SAMPLE), duration_sec=meta["frames"] / (meta["fps"] or 30),
                          fps=meta["fps"], width=int(decoded.frames.shape[2]),
                          height=int(decoded.frames.shape[1]), frame_count=meta["frames"],
                          test_type=TestType.standard_walk)
    with timed(timings, "end_to_end_run_ms"):
        out = GaitPipeline().run(analysis_id=f"prof_{uuid.uuid4().hex[:6]}", case=case,
                                 video=video, test_type=TestType.standard_walk)
    with timed(timings, "json_serialize_ms"):
        out.result.model_dump_json()
    with timed(timings, "pdf_export_ms"):
        build_pdf_report(out.result, case)

    meta["selected_backend"] = out.result.model_info.selected_backend or out.result.pose_backend

    # --- Write report ---
    report = {"meta": meta, "timings_ms": timings}
    (OUT / "profile_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Gait pipeline profile", "",
             f"- sample: {meta['sample']}",
             f"- frames: {meta['frames']} @ {meta['fps']} fps",
             f"- selected_backend: {meta.get('selected_backend')}", "",
             "| stage | ms |", "| --- | ---: |"]
    for k, v in timings.items():
        lines.append(f"| {k} | {v if v >= 0 else 'n/a'} |")
    (OUT / "profile_report.md").write_text("\n".join(lines), encoding="utf-8")

    print("=== gait pipeline profile (ms) ===")
    print(f"sample: {meta['frames']} frames @ {meta['fps']} fps; selected={meta.get('selected_backend')}")
    for k, v in timings.items():
        print(f"  {k:28s}: {v if v >= 0 else 'n/a'}")
    print(f"\nWrote {OUT/'profile_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
