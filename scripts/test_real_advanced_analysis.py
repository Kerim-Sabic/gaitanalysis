"""Verify SAM2 + Depth are ACTIVE in a real upload analysis (not just verifiers).

    # start the API with helpers enabled, then:
    python scripts/test_real_advanced_analysis.py http://127.0.0.1:8010

Fails if SAM2/Depth are enabled on the server but the analysis reports
BLOCKED_RUNTIME (the verifier-vs-pipeline mismatch this guards against).
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


def _get(path, raw=False):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        b = r.read()
        return b if raw else json.loads(b)


def _post_json(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def _upload(case_id):
    b = "----horalixadv"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"case_id\"\r\n\r\n{case_id}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"test_type\"\r\n\r\nstandard_walk\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"walk_test.mp4\"\r\n"
            f"Content-Type: video/mp4\r\n\r\n").encode() + SAMPLE.read_bytes() + b"\r\n" + f"--{b}--\r\n".encode()
    req = urllib.request.Request(BASE + "/videos/upload", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def main() -> int:
    if not SAMPLE.exists():
        print(f"BLOCKED: sample video missing at {SAMPLE}")
        return 1
    checks: list[tuple[str, bool, str]] = []

    def chk(n, ok, d=""):
        checks.append((n, bool(ok), d))

    pc = _post_json("/cases", {"patient_code": "ADV", "age": 50, "indication": "advanced"})
    video = _upload(pc["id"])
    prog = _post_json("/analysis/start", {"video_id": video["id"]})
    aid = prog["analysis_id"]
    st = {}
    for _ in range(180):
        st = _get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    chk("real analysis completed", st.get("status") == "completed", st.get("error") or "")
    if st.get("status") != "completed":
        return _summary(checks)

    r = _get(f"/analysis/{aid}/result")
    mi = r["model_info"]
    helpers = mi.get("helper_models", {})
    sam2 = helpers.get("sam2", {})
    depth = helpers.get("depth", {})

    chk("simulated_data_used false", r["simulated_data_used"] is False)
    chk("selected backend real", str(r["analysis_mode"]).startswith("real_"), r["analysis_mode"])
    chk("metrics exist", len(r["metrics"]) > 0)

    # Guard against verifier-vs-pipeline mismatch.
    chk("SAM2 not BLOCKED_RUNTIME", mi.get("sam2_status") != "BLOCKED_RUNTIME", mi.get("sam2_status"))
    chk("SAM2 ACTIVE/WORKING", mi.get("sam2_status") == "WORKING" and sam2.get("used_in_analysis") is True,
        f"status={mi.get('sam2_status')} used={sam2.get('used_in_analysis')}")
    chk("SAM2 provenance in JSON", "frames_segmented" in sam2 and "processing_time_sec" in sam2,
        f"frames={sam2.get('frames_segmented')} ms={sam2.get('processing_time_sec')}")

    chk("Depth not BLOCKED_RUNTIME", mi.get("depth_status") != "BLOCKED_RUNTIME", mi.get("depth_status"))
    chk("Depth ACTIVE/WORKING", mi.get("depth_status") == "WORKING" and depth.get("used_in_analysis") is True,
        f"status={mi.get('depth_status')} used={depth.get('used_in_analysis')}")

    js = _get(f"/analysis/{aid}/report.json")
    chk("JSON helper provenance", js["model_info"].get("helper_models", {}).get("sam2", {}).get("status") == "WORKING")
    pdf = _get(f"/analysis/{aid}/report.pdf", raw=True)
    chk("PDF export", isinstance(pdf, bytes) and pdf[:4] == b"%PDF")

    return _summary(checks)


def _summary(checks) -> int:
    print("=== real advanced analysis ===")
    for n, ok, d in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}{(' — ' + d) if d else ''}")
    ok = all(c[1] for c in checks)
    if not ok:
        print("\nNote: start the API with HORALIX_ENABLE_SAM2=true and HORALIX_ENABLE_DEPTH=true,")
        print("in a venv where 'sam2' + 'hydra' + torch + transformers are importable.")
    print("\n" + ("REAL ADVANCED ANALYSIS VERIFIED" if ok else "BLOCKED: SAM2/Depth not active in real analysis"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
