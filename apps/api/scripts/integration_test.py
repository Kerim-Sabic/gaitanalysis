"""End-to-end HTTP test against a running server (default http://localhost:8000)."""
from __future__ import annotations

import json
import sys
import time
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
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    health = get("/health")
    print("health:", health["status"], "models:", health["models"])

    prog = post("/analysis/demo", {"preset": "asymmetric"})
    aid = prog["analysis_id"]
    print("started:", aid, prog["status"])

    for _ in range(60):
        st = get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.4)
    print("final status:", st["status"], "progress:", st["progress"])
    assert st["status"] == "completed", st.get("error")

    result = get(f"/analysis/{aid}/result")
    print("metrics:", len(result["metrics"]), "flags:",
          [f["name"] for f in result["clinical_flags"]])
    print("risk:", result["mobility_risk_support_score"], result["mobility_risk_band"])

    pose = get(f"/analysis/{aid}/pose")
    print("pose frames:", pose["frame_count"], "kp/frame:", len(pose["frames"][0]["keypoints"]))

    pdf = get(f"/analysis/{aid}/report.pdf", raw=True)
    print("pdf bytes:", len(pdf), "is_pdf:", pdf[:4] == b"%PDF")

    cases = get("/cases")
    print("cases:", len(cases))
    print("\nINTEGRATION OK")


if __name__ == "__main__":
    main()
