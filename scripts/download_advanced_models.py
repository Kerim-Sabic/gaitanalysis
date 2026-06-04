"""Download only small/public advanced model assets explicitly requested.

Default behavior downloads the small official Ultralytics pose checkpoint.
Large RTMW/SAM2/Depth weights are never downloaded implicitly.
"""
from __future__ import annotations

import argparse
import shutil
import urllib.request

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
ULTRALYTICS_URL = (
    "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n-pose.pt"
)
ULTRALYTICS_DEST = REPO_ROOT / "models/pose/ultralytics/yolov8n-pose.pt"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ultralytics", action="store_true")
    args = parser.parse_args()
    print(f"Ultralytics: {ULTRALYTICS_URL} -> {ULTRALYTICS_DEST}")
    if not args.dry_run and not ULTRALYTICS_DEST.exists():
        ULTRALYTICS_DEST.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(ULTRALYTICS_URL, timeout=60) as response:
            with ULTRALYTICS_DEST.open("wb") as output:
                shutil.copyfileobj(response, output)
    print("Large RTMW/SAM2/Depth weights are not downloaded by default.")
    print("Matching MMPose configs must come from the official MMPose repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
