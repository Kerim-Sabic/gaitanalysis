"""Founder confidence check — orchestrates the most important verifications.

    apps/api/.venv/Scripts/python.exe scripts/final_done_app_check.py --api http://127.0.0.1:8010 --full

Runs git safety, model inventory, vision-model verification, live preview
contract, complete app flow, reliability benchmark, strict release check, Netlify
frontend check, and (with --full) the frontend build. Ends with DONE APP VERIFIED
or BLOCKED: <reason>. API-dependent checks need a running server (--api).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
PY = sys.executable
WEIGHT_EXTS = (".task", ".pt", ".pth", ".ckpt", ".safetensors", ".pth.tar", ".onnx")
MEDIA_EXTS = (".mp4", ".mov", ".mkv", ".avi")


def _git_safety() -> tuple[bool, str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    bad = [f for f in out.stdout.splitlines()
           if f.lower().endswith(WEIGHT_EXTS + MEDIA_EXTS + (".pdf",))]
    return (not bad, "clean" if not bad else f"TRACKED: {bad[:5]}")


def _script(path_parts, args) -> tuple[bool, str]:
    cmd = [PY, str(REPO_ROOT.joinpath(*path_parts))] + args
    r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=900)
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return (r.returncode == 0, tail[-1][:80] if tail else f"exit {r.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=None)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    rows: list[tuple[str, bool, str, float]] = []

    def run(name, fn):
        t = time.perf_counter()
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        rows.append((name, ok, detail, round(time.perf_counter() - t, 1)))

    run("git safety", _git_safety)
    run("model inventory", lambda: _script(["scripts", "model_inventory.py"], []))
    run("verify all vision models", lambda: _script(["scripts", "verify_all_vision_models.py"], []))
    run("reliability benchmark", lambda: _script(["scripts", "benchmark_gait_reliability.py"], []))
    run("netlify frontend check", lambda: _script(["scripts", "check_netlify_frontend.py"], []))

    if args.api:
        run("live preview contract", lambda: _script(["scripts", "test_live_preview_contract.py"], [args.api]))
        run("complete app flow", lambda: _script(["scripts", "test_complete_app_flow.py"], [args.api]))
        run("phone capture flow", lambda: _script(["scripts", "test_phone_capture_flow.py"], [args.api]))
        run("analysis setup + preflight",
            lambda: _script(["scripts", "test_analysis_setup_preflight.py"], [args.api]))
        run("per-request model selection",
            lambda: _script(["scripts", "test_advanced_mode_request.py"], [args.api]))
        # When advanced helpers are enabled, they MUST be active in real analysis.
        if str(os.environ.get("HORALIX_ENABLE_SAM2", "")).lower() in ("1", "true", "yes") or \
           str(os.environ.get("HORALIX_ENABLE_DEPTH", "")).lower() in ("1", "true", "yes"):
            run("real advanced analysis (SAM2/Depth active)",
                lambda: _script(["scripts", "test_real_advanced_analysis.py"], [args.api]))
        run("release_check strict", lambda: _script(
            ["scripts", "release_check.py"], ["--api", args.api, "--strict"] + (["--full"] if args.full else [])))
    else:
        rows.append(("api checks", True, "skipped (no --api)", 0.0))

    if args.full:
        def _build():
            r = subprocess.run(["npm", "run", "build"], cwd=REPO_ROOT / "apps" / "web",
                               capture_output=True, text=True, shell=(sys.platform == "win32"), timeout=900)
            return (r.returncode == 0, "build ok" if r.returncode == 0 else "build FAILED")
        run("frontend build", _build)

    print("\n=== FINAL DONE-APP CHECK ===")
    print(f"{'CHECK':30s} {'RESULT':6s} {'s':>7s}  detail")
    blockers = []
    for name, ok, detail, secs in rows:
        print(f"{name:30s} {'PASS' if ok else 'FAIL':6s} {secs:7.1f}  {detail}")
        if not ok:
            blockers.append(name)

    if blockers:
        print("\nBLOCKED: " + ", ".join(blockers))
        return 1
    print("\nDONE APP VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
