"""Report WHAM 3D status honestly (licensed SMPL assets required; never faked)."""
from __future__ import annotations

from _vision import print_result, working_exit  # noqa: F401


def verify():
    from app.pipeline.pose.wham_adapter import WHAMAdapter

    return WHAMAdapter.status()


if __name__ == "__main__":
    result = verify()
    print_result(result)
    raise SystemExit(0 if result["status"] in ("WORKING", "PARTIAL", "NOT_REQUIRED") else 1)
