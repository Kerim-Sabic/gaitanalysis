# Model weights

Heavy model checkpoints are **not** committed. Drop weights here and point the
adapters at them (or let the adapters download into their own caches).

```
models/
  pose/          RTMPose / RTMW3D / ViTPose checkpoints (MMPose, etc.)
  segmentation/  SAM 2 checkpoints
  tracking/      RTMDet / ByteTrack weights (optional, raw-frame multi-person)
  gait/          any trained gait classifiers / normative models (future)
```

Wiring:
- Pose → `apps/api/app/pipeline/pose/` adapters (`mmpose_adapter.py`, …)
- Segmentation → `apps/api/app/pipeline/segmentation/sam2_adapter.py`
- Selection → `HORALIX_POSE_BACKEND` (see `apps/api/app/config.py`)

Until weights + adapters are wired, the system runs in simulated/demo mode and
labels output accordingly. See [../docs/architecture.md](../docs/architecture.md).
