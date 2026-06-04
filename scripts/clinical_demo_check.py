"""Clinical demo verification against a running API.

    python scripts/clinical_demo_check.py http://127.0.0.1:8010

Confirms the clinical demo path: real analysis with metrics, clinical flags,
capture quality, model provenance, advanced-model statuses, PDF+disclaimer, JSON
clinical fields, safe (non-diagnostic) language, no simulated data in real mode.
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

# Disease labels that must NOT appear as conclusions in generated text.
FORBIDDEN = ["parkinson", "stroke gait", "cerebellar", "neuropathy", "hip oa",
             "acl injury", "diagnoses ", "has parkinson", "will fall"]


def _get(path, raw=False):
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        data = r.read()
        return data if raw else json.loads(data)


def _post_json(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _upload(case_id):
    b = "----horalixclin"
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

    chk("api health", _get("/")["status"] == "ok")

    pc = _post_json("/cases", {"patient_code": "CLIN", "age": 62, "indication": "clinical demo"})
    video = _upload(pc["id"])
    prog = _post_json("/analysis/start", {"video_id": video["id"]})
    aid = prog["analysis_id"]
    st = {}
    for _ in range(150):
        st = _get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    chk("real analysis completed", st.get("status") == "completed", st.get("error") or "")
    if st.get("status") != "completed":
        return _summary(checks)

    r = _get(f"/analysis/{aid}/result")
    mi = r["model_info"]
    chk("metrics exist", len(r["metrics"]) > 0, f"{len(r['metrics'])}")
    chk("clinical flags exist", len(r["clinical_flags"]) > 0, f"{len(r['clinical_flags'])}")
    chk("capture quality present", "overall_score" in r["quality"] and "status" in r["quality"],
        str(r["quality"].get("status")))
    chk("model provenance present", bool(mi.get("selected_backend")), mi.get("selected_backend", ""))
    chk("advanced statuses present", all(k in mi for k in
        ("sam2_status", "mmpose_status", "depth_status", "wham_status")),
        f"sam2={mi.get('sam2_status')} mmpose={mi.get('mmpose_status')} depth={mi.get('depth_status')} wham={mi.get('wham_status')}")
    chk("no simulated data (real)", r["simulated_data_used"] is False)
    chk("limitations present", len(r["limitations"]) > 0, f"{len(r['limitations'])}")

    text = " ".join([r.get("report_summary", ""), r.get("patient_summary", ""),
                     " ".join(f["explanation"] for f in r["clinical_flags"]),
                     " ".join(f["name"] for f in r["clinical_flags"])]).lower()
    bad = [t for t in FORBIDDEN if t in text]
    chk("no diagnosis language", not bad, f"found: {bad}" if bad else "clean")
    chk("disclaimer present", "standalone diagnostic" in (r.get("report_summary", "").lower()
                                                          + " ".join(r["limitations"]).lower()))

    pdf = _get(f"/analysis/{aid}/report.pdf", raw=True)
    chk("PDF report", pdf[:4] == b"%PDF" and len(pdf) > 1000, f"{len(pdf)}B")
    js = _get(f"/analysis/{aid}/report.json")
    chk("JSON clinical fields", all(k in js for k in ("metrics", "clinical_flags", "quality", "model_info", "limitations")))

    return _summary(checks)


def _summary(checks) -> int:
    print("=== clinical demo check ===")
    for n, ok, d in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}{(' — ' + d) if d else ''}")
    ok = all(c[1] for c in checks)
    print("\n" + ("CLINICAL DEMO CHECK VERIFIED" if ok else "BLOCKED: clinical demo checks failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
