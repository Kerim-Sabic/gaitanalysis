# Advanced Model Runtime

The verified MediaPipe/Ultralytics app environment remains
`apps/api/.venv`. Advanced models run in ignored isolated environments or
Docker verification profiles so their heavier dependencies cannot destabilize
the baseline.

## Verified Local Runtimes

Run all commands from the repository root:

```powershell
apps/api/.venv/Scripts/python.exe scripts/verify_sam2.py
apps/api/.venv/Scripts/python.exe scripts/verify_depth_anything.py
apps/api/.venv/Scripts/python.exe scripts/verify_mmpose.py
apps/api/.venv/Scripts/python.exe scripts/verify_wham.py
apps/api/.venv/Scripts/python.exe scripts/verify_all_vision_models.py
apps/api/.venv/Scripts/python.exe scripts/model_inventory.py
```

The verifiers automatically delegate to:

- `apps/api/.venv-sam2` for real SAM2.1 Tiny segmentation
- `apps/api/.venv-depth` for real Depth Anything V2 Small relative depth
- `apps/api/.venv-mmpose` for RTMW dependency/config/runtime verification

SAM2 and Depth are optional helpers. Enable them only in a runtime that has
their dependencies:

```powershell
$env:HORALIX_ENABLE_SAM2="true"
$env:HORALIX_ENABLE_DEPTH="true"
```

Depth Anything output is relative monocular depth only. It is never treated as
clinical distance or camera calibration.

## Docker Verification Profiles

Start Docker Desktop, then run one profile at a time:

```powershell
docker compose --profile mmpose up --build api-mmpose
docker compose --profile sam2 up --build api-sam2
docker compose --profile depth up --build api-depth
docker compose --profile vision up --build api-vision
```

These profiles mount `models/` and `data/` read-only, run the corresponding
real-inference verifier, and exit. They do not start the frontend or modify the
verified app venv.

## Exact Remaining Blockers

- **MMPose RTMW on Windows:** local dependencies, matching RTMW config,
  checkpoint, and Ultralytics detector are present, but full compiled
  `mmcv._ext` operations are unavailable. Run the Linux `api-mmpose` profile.
- **RTMW3D:** checkpoint is present; matching verified 3D config and
  `PoseSequence` mapping are not enabled.
- **WHAM:** requires the licensed
  `models/body_models/smpl/SMPL_NEUTRAL.pkl` asset from
  <https://smpl.is.tue.mpg.de>. The project does not download or commit it.

No model is reported `WORKING` unless its verifier loads the model, runs real
sample inference, and detects non-empty output.
