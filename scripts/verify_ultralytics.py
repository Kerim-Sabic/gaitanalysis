"""Verify real Ultralytics pose inference and PoseSequence conversion."""
from __future__ import annotations

from _vision import print_result, verify_pose_backend, working_exit


def verify():
    return verify_pose_backend("Ultralytics Pose")


if __name__ == "__main__":
    result = verify()
    print_result(result)
    raise SystemExit(working_exit(result))
