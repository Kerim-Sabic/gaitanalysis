"""End-to-end HTTP test against a running server (default http://localhost:8000)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def get(path, raw=False):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        data = r.read()
        return data if raw else json.loads(data)


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    health = get("/health")
    print("health:", health["status"], "| real_available:", health["models"]["real_analysis_available"])

    ms = get("/models/status")
    print("models/status: active=", ms["active_backend"], "real_available=", ms["real_analysis_available"],
          "loaded=", ms["model_loaded"])
    mv = get("/models/verify")
    print("models/verify: passed=", mv["passed"], "landmarks=", mv["landmarks_detected"],
          "err=", (mv.get("error") or "")[:50])

    # Demo flow (simulated keypoints; real pipeline measures them).
    _, prog = post("/analysis/demo", {"preset": "asymmetric"})
    aid = prog["analysis_id"]
    for _ in range(60):
        st = get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.4)
    print("demo status:", st["status"])
    assert st["status"] == "completed", st.get("error")

    result = get(f"/analysis/{aid}/result")
    print("  analysis_mode:", result["analysis_mode"], "| simulated_data_used:",
          result["simulated_data_used"], "| pose_backend:", result["pose_backend"])
    print("  metrics:", len(result["metrics"]), "| keypoint_stats:", len(result["keypoint_stats"]))
    cad = next(m for m in result["metrics"] if m["key"] == "cadence_steps_per_min")
    print("  cadence conf:", cad["confidence"], "| source_keypoints:", cad["source_keypoints"])
    print("  confidence_reason:", cad["confidence_reason"][:70])

    kp = get(f"/analysis/{aid}/keypoints")
    print("  /keypoints: stats=", len(kp["keypoint_stats"]), "| frames=", kp["track"]["frame_count"])
    mstat = get(f"/analysis/{aid}/model-status")
    print("  /model-status: model_loaded=", mstat["model_info"]["model_loaded"],
          "verified=", mstat["model_info"]["model_verified"])

    pdf = get(f"/analysis/{aid}/report.pdf", raw=True)
    print("  pdf bytes:", len(pdf), "is_pdf:", pdf[:4] == b"%PDF")

    # Real-analysis start behaviour depends on whether a real backend is available:
    #  - real available  -> 200 (job starts); on a synthetic demo clip the real
    #    model finds no person and the job fails with code no_person (honest).
    #  - real unavailable -> 422 model_unavailable (no silent fallback).
    video_id = result["video_id"]
    code, body = post("/analysis/start", {"video_id": video_id})
    detail = body.get("detail")
    if code == 200:
        raid = body["analysis_id"]
        for _ in range(40):
            rst = get(f"/analysis/{raid}/status")
            if rst["status"] in ("completed", "failed"):
                break
            time.sleep(0.4)
        print("real start: 200 ->", rst["status"], "| error:", (rst.get("error") or "")[:60])
    else:
        code_str = detail.get("code") if isinstance(detail, dict) else detail
        print("real start:", code, "| code:", code_str)

    print("\nINTEGRATION OK")


if __name__ == "__main__":
    main()
