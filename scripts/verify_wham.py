"""Report WHAM status honestly; licensed SMPL assets are never downloaded."""
from __future__ import annotations

import json
import sys

from _vision import print_result


def verify():
    from app.pipeline.pose.wham_adapter import WHAMAdapter

    return WHAMAdapter.status()


if __name__ == "__main__":
    result = verify()
    if "--json" in sys.argv:
        print(json.dumps(result))
    else:
        print_result(result)
    raise SystemExit(0 if result["status"] == "WORKING" else 1)
