"""Verify RTMW and report exact OpenMMLab/config blockers."""
from __future__ import annotations

from _vision import print_result, verify_pose_backend


def verify():
    return {
        "rtmw": verify_pose_backend("MMPose RTMW"),
        "rtmw3d": verify_pose_backend("MMPose RTMW3D"),
    }


if __name__ == "__main__":
    results = verify()
    print_result(results["rtmw"])
    print()
    print_result(results["rtmw3d"])
    raise SystemExit(0 if results["rtmw"]["status"] == "WORKING" else 1)
