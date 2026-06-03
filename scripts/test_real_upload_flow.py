"""End-to-end REAL upload flow against a running API.

    python scripts/test_real_upload_flow.py http://127.0.0.1:8010

Requires data/sample_videos/walk_test.mp4 AND a real backend available on the
server. Uploads the real video, runs real analysis, and asserts real provenance.
If the sample is missing it skips with status `sample_missing` (not a fake pass).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def _get(path, raw=False):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        data = r.read()
        return data if raw else json.loads(data)


def _post_json(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _post_multipart(path, fields, file_path, file_field="file"):
    boundary = "----horalixboundary12345"
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    fname = file_path.name
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
             f"filename=\"{fname}\"\r\nContent-Type: video/mp4\r\n\r\n").encode()
    body += file_path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def main() -> int:
    if not SAMPLE.exists():
        print(f"Sample video missing at {SAMPLE}. Skipping real upload flow.")
        print("STATUS: sample_missing")
        return 0

    status = _get("/models/status")
    if not status.get("real_analysis_available"):
        print("Server reports real analysis unavailable:",
              status.get("initialization_error"))
        print("STATUS: model_unavailable")
        return 1

    case = _post_json("/cases", {"patient_code": "REALTEST", "age": 40, "indication": "real flow"})
    video = _post_multipart("/videos/upload",
                            {"case_id": case["id"], "test_type": "standard_walk"}, SAMPLE)
    prog = _post_json("/analysis/start", {"video_id": video["id"]})
    aid = prog["analysis_id"]

    st = {}
    for _ in range(150):
        st = _get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    print("analysis status:", st.get("status"), st.get("error") or "")
    if st["status"] != "completed":
        print("STATUS: FAILED")
        return 1

    result = _get(f"/analysis/{aid}/result")
    kp = _get(f"/analysis/{aid}/keypoints")
    ms = _get(f"/analysis/{aid}/model-status")
    pdf = _get(f"/analysis/{aid}/report.pdf", raw=True)

    checks = {
        "analysis_mode real": result["analysis_mode"] in ("real_mediapipe_tasks", "real_ultralytics_pose"),
        "simulated_data_used false": result["simulated_data_used"] is False,
        "keypoints exist": kp["track"]["frame_count"] > 0,
        "valid_pose_frames>0": ms["model_info"]["valid_pose_frames"] > 0,
        "metrics exist": len(result["metrics"]) > 0,
        "model provenance": bool(ms["model_info"]["pose_model"]),
        "pdf %PDF": pdf[:4] == b"%PDF",
    }
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print("STATUS:", "FULL REAL VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
