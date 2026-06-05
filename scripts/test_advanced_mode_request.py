"""Verify per-request model selection actually controls the real analysis.

    # start the API (advanced runtime), then:
    python scripts/test_advanced_mode_request.py http://127.0.0.1:8010

Proves the pre-analysis setup options drive the pipeline (not just env vars):
  * Advanced Clinical request -> SAM2 + Depth ACTIVE when installed.
  * Expert request pinning a concrete pose backend -> that backend actually runs.
  * Explicit enable_sam2=False -> SAM2 NOT used (override wins in both directions).
  * Result provenance records requested-vs-actual model execution.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        return json.loads(r.read())


def _post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def _upload(case_id):
    b = "----horalixsetup"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"case_id\"\r\n\r\n{case_id}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"test_type\"\r\n\r\nstandard_walk\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"walk_test.mp4\"\r\n"
            f"Content-Type: video/mp4\r\n\r\n").encode() + SAMPLE.read_bytes() + b"\r\n" + f"--{b}--\r\n".encode()
    req = urllib.request.Request(BASE + "/videos/upload", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _run(video_id, options):
    prog = _post("/analysis/start", {"video_id": video_id, "options": options})
    aid = prog["analysis_id"]
    st = {}
    for _ in range(240):
        st = _get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    if st.get("status") != "completed":
        return None, st.get("error") or "did not complete"
    return _get(f"/analysis/{aid}/result"), ""


def main() -> int:
    if not SAMPLE.exists():
        print(f"BLOCKED: sample video missing at {SAMPLE}")
        return 1

    caps = _get("/models/capabilities")
    pose = {c["id"]: c for c in caps["pose_backends"]}
    helpers = {c["id"]: c for c in caps["helpers"]}
    sam2_avail = helpers["sam2"]["available"]
    depth_avail = helpers["depth"]["available"]
    # A concrete (non-auto) backend that is actually available, for pinning.
    pinned = next((bid for bid in ("mediapipe_tasks_full", "mediapipe_tasks_heavy",
                                   "ultralytics_pose") if pose.get(bid, {}).get("available")), None)

    checks: list[tuple[str, bool, str]] = []

    def chk(n, ok, d=""):
        checks.append((n, bool(ok), d))

    pc = _post("/cases", {"patient_code": "SETUP", "age": 50, "indication": "setup test"})
    video = _upload(pc["id"])

    # 1) Advanced Clinical -> helpers active when installed.
    res, err = _run(video["id"], {"analysis_quality_mode": "advanced_clinical",
                                  "capture_source": "upload", "protocol": "standard_walk"})
    chk("advanced analysis completed", res is not None, err)
    if res:
        mi = res["model_info"]
        ex = mi.get("model_execution", {})
        rq = mi.get("analysis_request", {})
        chk("provenance records advanced quality mode", rq.get("analysis_quality_mode") == "advanced_clinical",
            str(rq.get("analysis_quality_mode")))
        chk("provenance records capture source", rq.get("capture_source") == "upload")
        if sam2_avail:
            chk("advanced -> SAM2 active (per request, no env needed)",
                mi.get("sam2_status") == "WORKING" and ex.get("sam2_active") is True,
                f"status={mi.get('sam2_status')} active={ex.get('sam2_active')}")
        else:
            chk("SAM2 unavailable -> honestly not active", ex.get("sam2_active") is False)
        if depth_avail:
            chk("advanced -> Depth active (per request)",
                mi.get("depth_status") == "WORKING" and ex.get("depth_active") is True,
                f"status={mi.get('depth_status')} active={ex.get('depth_active')}")
        else:
            chk("Depth unavailable -> honestly not active", ex.get("depth_active") is False)

    # 2) Expert pin a concrete backend -> that backend actually runs.
    if pinned:
        res2, err2 = _run(video["id"], {"analysis_quality_mode": "expert", "pose_backend": pinned,
                                        "require_selected_pose_backend": True,
                                        "enable_sam2": False, "enable_depth": False})
        chk(f"pinned backend analysis completed ({pinned})", res2 is not None, err2)
        if res2:
            ex2 = res2["model_info"].get("model_execution", {})
            chk(f"pinned backend honored -> {pinned} ran",
                ex2.get("pose_backend_actual") == pinned and ex2.get("pose_backend_honored") is True,
                f"actual={ex2.get('pose_backend_actual')}")
    else:
        chk("pin concrete backend (skipped — none available)", True)

    # 3) Explicit enable_sam2=False overrides any server default (off direction).
    res3, err3 = _run(video["id"], {"analysis_quality_mode": "expert", "enable_sam2": False,
                                    "enable_depth": False})
    chk("explicit-off analysis completed", res3 is not None, err3)
    if res3:
        ex3 = res3["model_info"].get("model_execution", {})
        rq3 = res3["model_info"].get("analysis_request", {})
        chk("explicit enable_sam2=False -> SAM2 not active",
            ex3.get("sam2_active") is False and rq3.get("sam2_requested") is False,
            f"active={ex3.get('sam2_active')} requested={rq3.get('sam2_requested')}")

    print("=== per-request model selection ===")
    for n, ok, d in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}{(' — ' + d) if d else ''}")
    ok = all(c[1] for c in checks)
    if not ok:
        print("\nNote: start the API in the advanced runtime so SAM2/Depth are installable.")
    print("\n" + ("PER-REQUEST MODEL SELECTION VERIFIED" if ok else "BLOCKED: per-request selection failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
