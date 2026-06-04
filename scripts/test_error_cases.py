"""Structured-error test: confirm clean errors (not stack traces) for bad input.

    python scripts/test_error_cases.py http://127.0.0.1:8010
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

import _bootstrap  # noqa: F401

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def _req(method, path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _json(path, payload):
    return _req("POST", path, json.dumps(payload).encode(), {"Content-Type": "application/json"})


def _multipart_text(path):
    b = "----horalixerr"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"case_id\"\r\n\r\nnope\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.txt\"\r\n"
            f"Content-Type: text/plain\r\n\r\nnot a video\r\n--{b}--\r\n").encode()
    return _req("POST", path, body, {"Content-Type": f"multipart/form-data; boundary={b}"})


def main() -> int:
    cases = []

    code, _ = _json("/analysis/start", {"video_id": "does_not_exist"})
    cases.append(("start unknown video -> 404", code == 404))

    code, _ = _req("GET", "/analysis/bogus_id/result")
    cases.append(("result unknown id -> 404", code == 404))

    code, _ = _json("/analysis/demo", {"preset": "not_a_preset"})
    cases.append(("demo bad preset -> 400", code == 400))

    code, _ = _multipart_text("/videos/upload")
    cases.append(("upload non-video -> 4xx", 400 <= code < 500))

    code, body = _req("POST", "/live/frame")  # missing required file
    cases.append(("live frame no file -> 422", code in (400, 422)))

    code, _ = _req("GET", "/cases/nope")
    cases.append(("get unknown case -> 404", code == 404))

    for name, ok in cases:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    ok = all(v for _, v in cases)
    print("STATUS:", "ERROR HANDLING VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
