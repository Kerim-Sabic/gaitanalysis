"""Complete end-to-end app flow against a running API.

    python scripts/test_complete_app_flow.py http://127.0.0.1:8010

Exercises the full user-supported backend path: health -> live status -> models
status -> live frame (real) -> upload sample -> full analysis -> result assertions
-> keypoints -> model-status -> JSON -> PDF (+ disclaimer) -> no demo contamination.
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


def _multipart(path, fields, file_field, filename, content, ctype):
    b = "----horalixflow"
    body = b""
    for k, v in fields.items():
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
             f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode() + content + b"\r\n"
    body += f"--{b}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _live_frame_jpeg() -> bytes | None:
    if not SAMPLE.exists():
        return None
    import cv2
    cap = cv2.VideoCapture(str(SAMPLE))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 150
    out = None
    for frac in (0.55, 0.45, 0.65):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * frac))
        ok, frame = cap.read()
        if ok and frame is not None:
            out = cv2.imencode(".jpg", frame)[1].tobytes()
            break
    cap.release()
    return out


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def chk(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    if not SAMPLE.exists():
        print(f"BLOCKED: sample video missing at {SAMPLE}")
        return 1

    chk("api health", _get("/")["status"] == "ok")
    ls = _get("/live/status")
    chk("live status available", ls.get("available") is True, ls.get("backend", ""))
    ms = _get("/models/status")
    chk("models real available", ms.get("real_analysis_available") is True, ms.get("active_backend", ""))

    # Live frame on a real frame.
    jpeg = _live_frame_jpeg()
    if jpeg:
        lf = _multipart("/live/frame?frame_index=1", {}, "file", "frame.jpg", jpeg, "image/jpeg")
        chk("live frame keypoints", isinstance(lf.get("keypoints"), list) and len(lf["keypoints"]) >= 17)
        chk("live frame confidence>0", lf.get("mean_confidence", 0) > 0, str(lf.get("mean_confidence")))
        chk("live frame backend real", "mediapipe" in lf.get("backend", "") or "ultralytics" in lf.get("backend", ""))
        chk("live frame not simulated", lf.get("simulated_data_used") is False)

    # Upload + full analysis.
    pc = _post_json("/cases", {"patient_code": "FLOW", "age": 40, "indication": "complete flow"})
    video = _multipart("/videos/upload", {"case_id": pc["id"], "test_type": "standard_walk"},
                       "file", "walk_test.mp4", SAMPLE.read_bytes(), "video/mp4")
    prog = _post_json("/analysis/start", {"video_id": video["id"]})
    aid = prog["analysis_id"]
    st = {}
    for _ in range(150):
        st = _get(f"/analysis/{aid}/status")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    chk("analysis completed", st.get("status") == "completed", st.get("error") or "")
    if st.get("status") != "completed":
        _summary(checks)
        return 1

    r = _get(f"/analysis/{aid}/result")
    mi = r["model_info"]
    chk("analysis_mode real", r["analysis_mode"].startswith("real_"), r["analysis_mode"])
    chk("simulated_data_used false", r["simulated_data_used"] is False)
    chk("keypoint_source real", r["keypoint_source"] == "real_video_inference")
    chk("selected_backend present", bool(mi.get("selected_backend")), mi.get("selected_backend", ""))
    chk("valid_pose_frames>0", mi.get("valid_pose_frames", 0) > 0, str(mi.get("valid_pose_frames")))
    chk("avg confidence>0", mi.get("mean_keypoint_confidence", 0) > 0, str(mi.get("mean_keypoint_confidence")))
    chk("metrics present", len(r["metrics"]) > 0, f"{len(r['metrics'])} metrics")
    chk("gait events or limitation", len(r["events"]) > 0 or len(r["limitations"]) > 0)
    lr = {m["key"] for m in r["metrics"]}
    chk("left/right metrics", "left_step_time_sec" in lr and "right_step_time_sec" in lr)
    chk("joint ROM present", any("rom" in k for k in lr))
    chk("per-metric confidence", all("confidence" in m for m in r["metrics"]))
    chk("model transparency", bool(mi.get("selection_reason")) or bool(mi.get("backend_scores")))

    kp = _get(f"/analysis/{aid}/keypoints")
    chk("keypoints endpoint", kp["track"]["frame_count"] > 0)
    mstat = _get(f"/analysis/{aid}/model-status")
    chk("model-status endpoint", bool(mstat["model_info"]["pose_model"]))
    js = _get(f"/analysis/{aid}/report.json")
    chk("JSON export", js["analysis_id"] == aid)
    pdf = _get(f"/analysis/{aid}/report.pdf", raw=True)
    chk("PDF %PDF", pdf[:4] == b"%PDF" and len(pdf) > 1000, f"{len(pdf)}B")
    disclaimer_text = (js.get("report_summary", "") + " ".join(js.get("limitations", []))).lower()
    chk("disclaimer present", "standalone diagnostic" in disclaimer_text or "diagnostic decision" in disclaimer_text)
    chk("no demo contamination", r["pose_backend"] != "demo" and not r["simulated_data_used"])

    return _summary(checks)


def _summary(checks) -> int:
    print("=== complete app flow ===")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    ok = all(c[1] for c in checks)
    print("\n" + ("COMPLETE APP FLOW VERIFIED" if ok else "BLOCKED: one or more flow checks failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
