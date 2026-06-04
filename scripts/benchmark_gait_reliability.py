"""Technical reliability benchmark: run the same sample 3x and compare.

    python scripts/benchmark_gait_reliability.py

Runs the verified pipeline on data/sample_videos/walk_test.mp4 three times and
checks repeatability (no clinical-accuracy claim — there is no ground-truth set).
Pass if backend selection is stable, valid-pose-frame count and mean confidence
are stable within tolerance, key metrics are not wildly different, and runtime is
not extreme. Ends with GAIT RELIABILITY VERIFIED or BLOCKED.
"""
from __future__ import annotations

import time
import uuid

import numpy as np

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
RUNS = 3


def _metric(result, key):
    m = next((m for m in result.metrics if m.key == key), None)
    return m.value if m else None


def main() -> int:
    if not SAMPLE.exists():
        print(f"BLOCKED: sample video missing at {SAMPLE}")
        return 1

    from app.pipeline.orchestrator import GaitPipeline
    from app.schemas import PatientCase, TestType, VideoMetadata

    pipeline = GaitPipeline()
    rows = []
    for i in range(RUNS):
        case = PatientCase(id=f"bench{i}", patient_code="BENCH", age=40, height_cm=172)
        video = VideoMetadata(id=f"benchv{i}", case_id=f"bench{i}", filename="walk_test.mp4",
                              stored_path=str(SAMPLE), duration_sec=5.2, fps=30,
                              width=1280, height=720, frame_count=156,
                              test_type=TestType.standard_walk)
        t0 = time.perf_counter()
        out = pipeline.run(analysis_id=f"bench_{uuid.uuid4().hex[:6]}", case=case,
                           video=video, test_type=TestType.standard_walk)
        rt = time.perf_counter() - t0
        r = out.result
        rows.append({
            "backend": r.model_info.selected_backend or r.pose_backend,
            "valid": r.model_info.valid_pose_frames,
            "conf": r.model_info.mean_keypoint_confidence,
            "cadence": _metric(r, "cadence_steps_per_min"),
            "steps": _metric(r, "step_count"),
            "step_asym": next((a.asymmetry_percent for a in r.asymmetry
                               if a.key == "step_time_asymmetry"), None),
            "runtime_s": round(rt, 2),
            "simulated": r.simulated_data_used,
        })

    print("=== gait reliability (3 runs) ===")
    for i, row in enumerate(rows):
        print(f"  run {i+1}: {row}")

    def vals(k):
        return [r[k] for r in rows if r[k] is not None]

    def stable(k, tol_frac):
        v = vals(k)
        if len(v) < RUNS:
            return False
        mean = np.mean(v)
        return mean == 0 or (max(v) - min(v)) <= tol_frac * abs(mean) + 1e-9

    checks = {
        "backend stable": len({r["backend"] for r in rows}) == 1,
        "no demo contamination": all(r["simulated"] is False for r in rows),
        "valid frames stable (±10%)": stable("valid", 0.10),
        "confidence stable (±10%)": stable("conf", 0.10),
        "cadence stable (±15%)": stable("cadence", 0.15),
        "step count stable (±15%)": stable("steps", 0.15),
        "runtime not extreme (<60s)": all(r["runtime_s"] < 60 for r in rows),
    }
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print("\n" + ("GAIT RELIABILITY VERIFIED" if ok else "BLOCKED: reliability variance too high"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
