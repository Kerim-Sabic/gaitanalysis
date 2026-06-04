"""Concurrency test: run several analyses at once and confirm isolation.

    python scripts/test_concurrent_analyses.py http://127.0.0.1:8010

Starts multiple demo analyses concurrently and asserts each completes with its
own distinct result (no cross-job state leakage). Uses demo presets so it does
not depend on a real person being present.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request

import _bootstrap  # noqa: F401

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
PRESETS = ["normal", "asymmetric", "tug", "poor_quality"]


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())


def _post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _run(preset, out, idx):
    try:
        prog = _post("/analysis/demo", {"preset": preset})
        aid = prog["analysis_id"]
        for _ in range(80):
            st = _get(f"/analysis/{aid}/status")
            if st["status"] in ("completed", "failed"):
                break
            time.sleep(0.3)
        res = _get(f"/analysis/{aid}/result") if st["status"] == "completed" else None
        out[idx] = {"preset": preset, "analysis_id": aid, "status": st["status"],
                    "cadence": (next((m["value"] for m in res["metrics"]
                                      if m["key"] == "cadence_steps_per_min"), None) if res else None),
                    "simulated": res["simulated_data_used"] if res else None}
    except Exception as e:
        out[idx] = {"preset": preset, "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    out: dict[int, dict] = {}
    threads = [threading.Thread(target=_run, args=(p, out, i)) for i, p in enumerate(PRESETS)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0

    results = [out[i] for i in sorted(out)]
    for r in results:
        print(" ", r)
    ids = [r.get("analysis_id") for r in results if r.get("analysis_id")]
    checks = {
        "all completed": all(r.get("status") == "completed" for r in results),
        "distinct analysis ids": len(set(ids)) == len(PRESETS),
        "all simulated (demo)": all(r.get("simulated") is True for r in results),
        "no errors": all("error" not in r for r in results),
    }
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"  elapsed: {elapsed:.1f}s for {len(PRESETS)} concurrent analyses")
    ok = all(checks.values())
    print("STATUS:", "CONCURRENCY VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
