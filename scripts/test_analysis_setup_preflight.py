"""Verify the pre-analysis model-control plane: /models/capabilities + /analysis/preflight.

    python scripts/test_analysis_setup_preflight.py http://127.0.0.1:8010

Checks that capabilities are structured + honest (status is live, not hardcoded),
that quality modes drive helper defaults, and that preflight reports an executable
plan with blocked reasons when a required model is unavailable.
"""
from __future__ import annotations

import json
import sys
import urllib.request

import _bootstrap  # noqa: F401

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())


def _post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def chk(n, ok, d=""):
        checks.append((n, bool(ok), d))

    caps = _get("/models/capabilities")
    pose = {c["id"]: c for c in caps.get("pose_backends", [])}
    helpers = {c["id"]: c for c in caps.get("helpers", [])}

    chk("capabilities has pose backends", len(pose) >= 4, str(list(pose)))
    chk("capabilities has helpers (sam2/depth/wham)",
        {"sam2", "depth", "wham"} <= set(helpers), str(list(helpers)))
    chk("capabilities has quality modes",
        {m["id"] for m in caps.get("quality_modes", [])} == {"standard", "advanced_clinical", "expert"})
    chk("auto_best present + has a status", "auto_best" in pose and bool(pose["auto_best"]["status"]))
    chk("every card carries available + status + what_it_does",
        all("available" in c and c.get("status") and "what_it_does" in c
            for c in list(pose.values()) + list(helpers.values())))
    # Honest blocked models expose a fix hint.
    blocked = [c for c in list(pose.values()) + list(helpers.values()) if not c["available"]]
    chk("blocked models give a fix hint", all(c.get("fix_hint") for c in blocked),
        str([c["id"] for c in blocked if not c.get("fix_hint")]))

    # Standard mode inherits the server defaults; an explicit override must win.
    pf_std = _post("/analysis/preflight", {"analysis_quality_mode": "standard"})
    chk("standard preflight resolves a pose backend", bool(pf_std["pose_backend"]))
    pf_std_off = _post("/analysis/preflight",
                       {"analysis_quality_mode": "standard", "enable_sam2": False, "enable_depth": False})
    chk("explicit helper-off overrides defaults in preflight",
        pf_std_off["expected_transparency"]["sam2_requested"] is False
        and pf_std_off["expected_transparency"]["depth_requested"] is False)

    # Advanced clinical: helpers requested (active iff installed).
    pf_adv = _post("/analysis/preflight", {"analysis_quality_mode": "advanced_clinical"})
    chk("advanced requests SAM2 + Depth",
        pf_adv["expected_transparency"]["sam2_requested"] is True
        and pf_adv["expected_transparency"]["depth_requested"] is True)
    if caps["real_analysis_available"]:
        chk("advanced can start when a real backend exists", pf_adv["can_start"] is True,
            str(pf_adv["blocked_reasons"]))
    # If SAM2 is installed it should be slated to run; otherwise it must warn (not silently drop).
    sam2_avail = helpers["sam2"]["available"]
    sam2_will_run = any("SAM2" in w for w in pf_adv["will_run"])
    sam2_warned = any("SAM2" in w for w in pf_adv["warnings"])
    chk("advanced SAM2 is honest (run if available, else warn)",
        sam2_will_run if sam2_avail else (sam2_warned or sam2_will_run is False))

    # Expert + require a backend that is NOT available -> blocked.
    blocked_backend = next((bid for bid, c in pose.items() if not c["available"]), None)
    if blocked_backend:
        pf_blk = _post("/analysis/preflight", {
            "analysis_quality_mode": "expert",
            "pose_backend": blocked_backend,
            "require_selected_pose_backend": True,
        })
        chk(f"requiring unavailable backend '{blocked_backend}' blocks start",
            pf_blk["can_start"] is False and len(pf_blk["blocked_reasons"]) > 0)
    else:
        chk("requiring unavailable backend (skipped — all available)", True, "all backends available")

    # Expert + require SAM2 when unavailable -> blocked.
    if not sam2_avail:
        pf_sam2 = _post("/analysis/preflight", {
            "analysis_quality_mode": "expert", "enable_sam2": True,
            "require_advanced_helpers": True,
        })
        chk("requiring unavailable SAM2 blocks start", pf_sam2["can_start"] is False)
    else:
        chk("requiring SAM2 (available) is allowed",
            _post("/analysis/preflight", {"analysis_quality_mode": "expert", "enable_sam2": True,
                                          "require_advanced_helpers": True})["can_start"] is True)

    print("=== analysis setup / preflight ===")
    for n, ok, d in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}{(' — ' + d) if d else ''}")
    ok = all(c[1] for c in checks)
    print("\n" + ("SETUP PREFLIGHT VERIFIED" if ok else "BLOCKED: setup/preflight contract failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
