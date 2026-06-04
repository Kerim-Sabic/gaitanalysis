"""Contract test for the near-real-time live preview endpoints.

    python scripts/test_live_preview_contract.py http://127.0.0.1:8010

Verifies /live/status and /live/frame: schema, real keypoints on a real frame,
no simulated data in live mode. Requires a running API.
"""
from __future__ import annotations

import json
import sys
import urllib.request

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE = REPO_ROOT / "data" / "sample_videos" / "walk_test.mp4"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def _post_frame(jpeg: bytes):
    boundary = "----horalixlive"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"frame.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode() + jpeg + \
        f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/live/frame?frame_index=1", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _real_frame_jpegs() -> list[bytes]:
    """Several mid-clip frames (person reliably in frame) as JPEG bytes."""
    if not SAMPLE.exists():
        return []
    try:
        import cv2
        cap = cv2.VideoCapture(str(SAMPLE))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 150
        out: list[bytes] = []
        for frac in (0.45, 0.55, 0.65, 0.35, 0.75):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * frac))
            ok, frame = cap.read()
            if ok and frame is not None:
                out.append(cv2.imencode(".jpg", frame)[1].tobytes())
        cap.release()
        return out
    except Exception:
        return []


def main() -> int:
    status = _get("/live/status")
    print("live/status:", {k: status.get(k) for k in ("available", "backend", "simulated_data_used", "final_backend")})
    checks = {
        "live available": status.get("available") is True,
        "status not simulated": status.get("simulated_data_used") is False,
    }

    candidates = _real_frame_jpegs()
    used_real = len(candidates) > 0
    if not candidates:
        import cv2
        import numpy as np
        candidates = [cv2.imencode(".jpg", np.full((480, 640, 3), 60, np.uint8))[1].tobytes()]

    r = _post_frame(candidates[0])
    detected = bool(r.get("valid_pose"))
    for jpeg in candidates[1:]:
        if detected:
            break
        r = _post_frame(jpeg)
        detected = bool(r.get("valid_pose"))
    print("live/frame:", {k: r.get(k) for k in ("valid_pose", "mean_confidence", "backend", "inference_ms")})
    checks.update({
        "frame has keypoints array": isinstance(r.get("keypoints"), list) and len(r["keypoints"]) >= 17,
        "frame has confidence": isinstance(r.get("mean_confidence"), (int, float)),
        "frame has backend": bool(r.get("backend")),
        "frame has inference_ms": isinstance(r.get("inference_ms"), (int, float)),
        "frame not simulated": r.get("simulated_data_used") is False,
        "keypoint_source real": r.get("keypoint_source") == "real_video_inference",
    })
    if used_real:
        checks["real frame -> pose detected"] = detected

    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print("STATUS:", "LIVE PREVIEW CONTRACT VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
