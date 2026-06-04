"""Verify RTMW in its isolated runtime and report exact blockers."""
from __future__ import annotations

import json
import sys

from _vision import print_result, run_isolated_verifier, verify_pose_backend


def verify():
    delegated = run_isolated_verifier("verify_mmpose.py", ".venv-mmpose")
    if delegated is not None:
        return delegated
    return {
        "rtmw": verify_pose_backend("MMPose RTMW"),
        "rtmw3d": verify_pose_backend("MMPose RTMW3D"),
    }


if __name__ == "__main__":
    results = verify()
    if "--json" in sys.argv:
        print(json.dumps(results))
    else:
        print_result(results["rtmw"])
        print()
        print_result(results["rtmw3d"])
    raise SystemExit(0 if results["rtmw"]["status"] == "WORKING" else 1)
