"""Standalone pipeline smoke test (no HTTP server).

Runs the real pipeline on each simulated demo preset and prints key metrics, so
we can confirm the gait math executes and produces sensible, *computed* values.

    python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.orchestrator import GaitPipeline  # noqa: E402
from app.schemas import PatientCase, TestType, VideoMetadata  # noqa: E402


def run(preset: str, test_type: TestType):
    case = PatientCase(id=f"case_{preset}", patient_code=f"DEMO-{preset}", age=60,
                       height_cm=172.0, indication="smoke test")
    video = VideoMetadata(id=f"video_{preset}", case_id=case.id,
                          filename=f"{preset}.mp4", stored_path="",
                          duration_sec=7.0, fps=30.0, width=1280, height=720,
                          frame_count=210, test_type=test_type)
    out = GaitPipeline().run(
        analysis_id=f"an_{preset}", case=case, video=video,
        test_type=test_type, demo_preset=preset,
    )
    r = out.result
    print(f"\n=== preset={preset} mode={r.analysis_mode.value} "
          f"quality={r.quality.overall_score:.0f} risk={r.mobility_risk_support_score:.0f}"
          f" ({r.mobility_risk_band}) conf={r.overall_confidence:.2f} ===")
    for key in ("cadence_steps_per_min", "step_count", "gait_cycles_detected",
                "walking_speed_m_per_s", "knee_rom_left_deg", "knee_rom_right_deg",
                "stride_time_variability"):
        m = r.metric(key)
        if m:
            print(f"  {m.label:24s}: {m.value} {m.unit}  (conf {m.confidence:.2f}) [{m.status.value}]")
    sa = next((a for a in r.asymmetry if a.key == "step_time_asymmetry"), None)
    if sa:
        print(f"  step-time asymmetry      : {sa.asymmetry_percent}%  [{sa.status.value}]")
    print(f"  events: {len(r.events)}   flags: {[f.name for f in r.clinical_flags]}")
    assert out.pose_track.frame_count > 0
    return r


if __name__ == "__main__":
    run("normal", TestType.standard_walk)
    run("asymmetric", TestType.standard_walk)
    run("poor_quality", TestType.standard_walk)
    run("tug", TestType.timed_up_and_go)
    print("\nSmoke test OK.")
