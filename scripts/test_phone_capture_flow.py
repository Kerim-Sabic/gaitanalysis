"""QR phone-capture flow test against a running API.

    python scripts/test_phone_capture_flow.py http://127.0.0.1:8010

Creates a pairing session, rejects bad/missing sessions, connects, uploads the
sample video through the mobile endpoint, polls to completion, and confirms real
(non-demo) analysis + PDF/JSON export.
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


def _call(method, path, data=None, headers=None, raw=False):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
            return r.status, (body if raw else json.loads(body))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def _upload(session_id, token):
    b = "----horalixphone"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"walk_test.mp4\"\r\nContent-Type: video/mp4\r\n\r\n").encode() + \
        SAMPLE.read_bytes() + b"\r\n" + f"--{b}--\r\n".encode()
    return _call("POST", f"/mobile/session/{session_id}/upload?token={token}", data=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})


def main() -> int:
    if not SAMPLE.exists():
        print(f"BLOCKED: sample video missing at {SAMPLE}")
        return 1
    checks: list[tuple[str, bool, str]] = []

    def chk(n, ok, d=""):
        checks.append((n, bool(ok), d))

    # Create the session WITH a chosen setup so the phone clip inherits it.
    setup = {"analysis_quality_mode": "advanced_clinical", "protocol": "neuro_gait_screen",
             "capture_source": "phone"}
    _, created = _call("POST", "/mobile/session", data=json.dumps(setup).encode(),
                       headers={"Content-Type": "application/json"})
    sid, token = created.get("session_id"), created.get("pairing_token")
    chk("create session", bool(sid and token), created.get("status", ""))
    chk("mobile_url_path present", "/mobile-capture/" in (created.get("mobile_url_path") or ""))

    # Security: missing session + invalid token rejected.
    code, _ = _call("GET", "/mobile/session/sess_does_not_exist?token=x")
    chk("unknown session -> 404", code == 404)
    code, _ = _call("GET", f"/mobile/session/{sid}?token=WRONGTOKEN")
    chk("invalid token -> 403", code == 403)
    code, body = _call("POST", f"/mobile/session/{sid}/upload?token=WRONGTOKEN")
    chk("invalid token upload rejected", code in (403, 422))

    # Connect + upload + poll.
    code, conn = _call("POST", f"/mobile/session/{sid}/connect?token={token}")
    chk("connect -> phone_connected", code == 200 and conn.get("status") == "phone_connected")
    code, up = _upload(sid, token)
    chk("phone upload -> analyzing", code == 200 and up.get("status") == "analyzing",
        up.get("analysis_id", ""))
    aid = up.get("analysis_id")

    st = {}
    for _ in range(150):
        _, st = _call("GET", f"/mobile/session/{sid}?token={token}")
        if st.get("status") in ("completed", "error", "expired", "cancelled"):
            break
        time.sleep(0.5)
    chk("session completed", st.get("status") == "completed", st.get("error") or st.get("status", ""))
    chk("session source_device phone", st.get("source_device") == "phone_capture")

    if st.get("status") == "completed" and aid:
        _, r = _call("GET", f"/analysis/{aid}/result")
        chk("analysis_mode real", str(r.get("analysis_mode", "")).startswith("real_"), r.get("analysis_mode"))
        chk("simulated_data_used false", r.get("simulated_data_used") is False)
        chk("keypoint_source real", r.get("keypoint_source") == "real_video_inference")
        chk("metrics generated", len(r.get("metrics", [])) > 0)
        # Setup inheritance: the phone clip ran with the desktop-chosen setup.
        rq = r.get("model_info", {}).get("analysis_request", {})
        chk("phone inherited quality mode", rq.get("analysis_quality_mode") == "advanced_clinical",
            str(rq.get("analysis_quality_mode")))
        chk("phone inherited capture source", rq.get("capture_source") == "phone",
            str(rq.get("capture_source")))
        chk("phone inherited protocol", r.get("test_type") == "neuro_gait_screen", r.get("test_type"))
        _, js = _call("GET", f"/analysis/{aid}/report.json")
        chk("JSON export", js.get("analysis_id") == aid)
        _, pdf = _call("GET", f"/analysis/{aid}/report.pdf", raw=True)
        chk("PDF export", isinstance(pdf, bytes) and pdf[:4] == b"%PDF")

    print("=== phone capture flow ===")
    for n, ok, d in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}{(' — ' + d) if d else ''}")
    ok = all(c[1] for c in checks)
    print("\n" + ("PHONE CAPTURE FLOW VERIFIED" if ok else "BLOCKED: phone capture flow failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
