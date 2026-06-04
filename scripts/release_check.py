"""Practical release-candidate check for Horalix Gait AI.

    python scripts/release_check.py
    python scripts/release_check.py --full
    python scripts/release_check.py --api http://127.0.0.1:8010
    python scripts/release_check.py --skip-frontend
    python scripts/release_check.py --profile

Ends with exactly one of:
    RELEASE-CANDIDATE VERIFIED
    BLOCKED: <reason>
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
WEIGHT_EXTS = (".task", ".pt", ".pth", ".ckpt", ".safetensors", ".pth.tar", ".onnx", ".bin", ".pkl")
MEDIA_EXTS = (".mp4", ".mov", ".mkv", ".avi")


class Check:
    def __init__(self):
        self.rows: list[tuple[str, bool, str, float]] = []
        self.blockers: list[str] = []

    def run(self, name: str, fn, blocking: bool = True):
        t = time.perf_counter()
        ok, detail = False, ""
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        ms = round((time.perf_counter() - t) * 1000.0, 1)
        self.rows.append((name, ok, detail, ms))
        if blocking and not ok:
            self.blockers.append(f"{name}: {detail}")


def _git_clean_of(exts) -> tuple[bool, str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    bad = [f for f in out.stdout.splitlines() if f.lower().endswith(tuple(exts))]
    return (len(bad) == 0, "none tracked" if not bad else f"TRACKED: {bad[:5]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=None)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--skip-frontend", action="store_true")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args()

    c = Check()

    # Git safety.
    c.run("git: no weights tracked", lambda: _git_clean_of(WEIGHT_EXTS))
    c.run("git: no videos tracked", lambda: _git_clean_of(MEDIA_EXTS))
    c.run("git: no reports tracked",
          lambda: _git_clean_of((".pdf",)) if True else (True, ""))

    # Sample video.
    c.run("sample video present", lambda: (SAMPLE.exists(), str(SAMPLE) if SAMPLE.exists() else "missing"))

    def _readable():
        from app.pipeline.video_processor import VideoProcessor
        d = VideoProcessor(max_frames=10).load(SAMPLE, min_seconds=0.2)
        return (d.frames.shape[0] > 0, f"{d.frames.shape[0]} frames @ {d.fps:.0f}fps")
    if SAMPLE.exists():
        c.run("sample video readable", _readable)

    # Backends.
    def _backends():
        from app.models import model_registry as reg
        avail = reg.available_real_backends()
        return (len(avail) > 0, f"available real: {avail}")
    c.run("real backend available", _backends)

    def _mediapipe():
        from app.pipeline.pose.mediapipe_adapter import (
            MediaPipeFullPoseEstimator, MediaPipeHeavyPoseEstimator)
        return (MediaPipeFullPoseEstimator.is_available() and MediaPipeHeavyPoseEstimator.is_available(),
                "Full+Heavy available")
    c.run("MediaPipe Full+Heavy", _mediapipe)

    def _ultra():
        from app.pipeline.pose.ultralytics_adapter import UltralyticsPoseEstimator
        return (True, "available" if UltralyticsPoseEstimator.is_available() else "not installed (optional)")
    c.run("Ultralytics (optional)", _ultra, blocking=False)

    # Pose detection on real sample (uses loader.verify -> requires landmarks).
    def _verify():
        from app.models.model_loader import get_model_loader
        v = get_model_loader().verify()
        ok = v.status == "passed" and v.valid_pose_frames > 0 and v.average_confidence > 0
        return (ok, f"status={v.status} valid={v.valid_pose_frames} conf={v.average_confidence} backend={v.backend}")
    c.run("real pose detection (sample)", _verify)

    # Demo smoke + PDF/JSON export (one real-ish path through the pipeline).
    def _demo_export():
        import uuid
        from app.pipeline.orchestrator import GaitPipeline
        from app.reporting import build_pdf_report
        from app.schemas import PatientCase, TestType, VideoMetadata
        case = PatientCase(id="rc", patient_code="RC", age=40, height_cm=172)
        video = VideoMetadata(id="rcv", case_id="rc", filename="d.mp4", stored_path="",
                              duration_sec=7, fps=30, width=1280, height=720,
                              frame_count=210, test_type=TestType.standard_walk)
        out = GaitPipeline().run(analysis_id=f"rc_{uuid.uuid4().hex[:6]}", case=case,
                                 video=video, test_type=TestType.standard_walk, demo_preset="normal")
        pdf = build_pdf_report(out.result, case)
        js = out.result.model_dump_json()
        return (pdf[:4] == b"%PDF" and len(js) > 100 and out.result.simulated_data_used,
                f"pdf={len(pdf)}B json={len(js)}B demo_separated={out.result.simulated_data_used}")
    c.run("demo + PDF/JSON export", _demo_export)

    # Release docs.
    def _docs():
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
        return ("Verified working path" in readme or "Real AI Vision Setup" in readme,
                "README setup section present")
    c.run("release docs present", _docs)

    # Optional: real HTTP upload flow.
    if args.api:
        def _http():
            r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "test_real_upload_flow.py"), args.api],
                               capture_output=True, text=True, cwd=REPO_ROOT)
            return (r.returncode == 0 and "FULL REAL VERIFIED" in r.stdout, r.stdout.strip().splitlines()[-1] if r.stdout else "no output")
        c.run("real HTTP upload flow", _http)

    # Optional: frontend build.
    if args.full and not args.skip_frontend:
        def _fe():
            r = subprocess.run(["npm", "run", "build"], cwd=REPO_ROOT / "apps" / "web",
                               capture_output=True, text=True, shell=(sys.platform == "win32"))
            return (r.returncode == 0, "build ok" if r.returncode == 0 else r.stderr.strip().splitlines()[-1:])
        c.run("frontend build", _fe)

    # Optional: profile.
    if args.profile:
        def _prof():
            r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "profile_gait_pipeline.py")],
                               capture_output=True, text=True, cwd=REPO_ROOT)
            return (r.returncode == 0, "profiled")
        c.run("profile pipeline", _prof, blocking=False)

    # Report.
    print("\n=== Horalix release check ===")
    print(f"{'CHECK':38s} {'RESULT':8s} {'ms':>8s}  detail")
    for name, ok, detail, ms in c.rows:
        print(f"{name:38s} {'PASS' if ok else 'FAIL':8s} {ms:8.1f}  {detail}")

    if c.blockers:
        print("\nBLOCKED: " + " | ".join(c.blockers))
        return 1
    print("\nRELEASE-CANDIDATE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
