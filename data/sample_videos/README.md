# Sample Videos for Full Real Verification

`data/sample_videos/walk_test.mp4` is the canonical real walking clip used by:

- `scripts/verify_models.py`
- `scripts/test_pose_on_sample_video.py`
- `scripts/test_real_upload_flow.py`
- `scripts/select_best_gait_sample.py`
- `scripts/test_multimodel_upload_flow.py`

MediaPipe Tasks can initialize and execute without this file, but **FULL REAL
VERIFIED** requires a real human video that returns valid pose landmarks and
feeds the real gait metrics pipeline.

Downloaded videos, processed videos, reports, and manual inputs are ignored by
git. Do not commit patient media or public dataset files.

## Automatic Download

The downloader uses the public Health&Gait Zenodo record and downloads only its
small `dataset_samples.zip` archive when available. It never downloads the full
26 GB+ dataset by default. The current Health&Gait sample archive contains
derived pose/flow/segmentation artifacts but no original RGB video, so use the
public GaHu source when an automatic real RGB sample is required.

```bash
python scripts/download_gait_sample_videos.py
python scripts/download_gait_sample_videos.py --source gahu --limit 3
python scripts/test_pose_on_sample_video.py
```

Windows PowerShell with the project virtual environment:

```powershell
apps/api/.venv/Scripts/python.exe scripts/download_gait_sample_videos.py
apps/api/.venv/Scripts/python.exe scripts/download_gait_sample_videos.py --source gahu --limit 3
apps/api/.venv/Scripts/python.exe scripts/test_pose_on_sample_video.py
```

Useful options:

```bash
python scripts/download_gait_sample_videos.py --dry-run
python scripts/download_gait_sample_videos.py --source healthgait --limit 3
python scripts/download_gait_sample_videos.py --process-manual
python scripts/download_gait_sample_videos.py --force
```

Generated reports:

- `data/sample_videos/reports/download_report.json`
- `data/sample_videos/reports/download_report.md`

After downloading/extracting candidates, run the real multi-backend selector:

```powershell
apps/api/.venv/Scripts/python.exe scripts/select_best_gait_sample.py
```

It evaluates every local raw/processed/manual candidate using every available
real pose backend, writes `best_sample_selection.json` and
`best_sample_selection.md`, and replaces `walk_test.mp4` only with the best
measured real candidate. A result below 0.35 mean confidence is explicitly
reported as weak rather than described as a perfect sample.

Health&Gait source: <https://zenodo.org/records/14039922>, licensed CC BY 4.0.

## Manual Download

If no automatic sample is available:

1. Open <https://data.mendeley.com/datasets/gprg4s73v4/1>.
2. Download the GaHu-Video dataset or a small edited gait video.
3. Choose a simple side-view walking clip, preferably a right/left track clip.
4. Place it in `data/sample_videos/manual_input/`.
5. Run:

```bash
python scripts/download_gait_sample_videos.py --process-manual
```

You can also place your own `.mp4`, `.avi`, `.mov`, or `.mkv` walking clip in
`data/sample_videos/manual_input/`.

## Required Video Quality

- Real human walking naturally across the frame
- One person only
- Side/sagittal view preferred
- Full body and feet visible throughout
- Stable camera and good lighting
- No heavy occlusion or crowd
- 5-15 seconds
- At least 480p preferred
- 24 FPS minimum; 30 FPS preferred

## Manual ffmpeg Conversion

```bash
ffmpeg -y -i input.avi -t 10 -vf "fps=30,scale='min(1280,iw)':-2" -an -movflags +faststart data/sample_videos/walk_test.mp4
```

The downloader uses H.264 through ffmpeg when available. If ffmpeg is missing or
H.264 conversion fails, it attempts an OpenCV MP4V fallback and records that
limitation in the download report.

## Verification

Run:

```bash
python scripts/test_pose_on_sample_video.py
```

FULL REAL VERIFIED requires all of the following:

1. `walk_test.mp4` exists and decodes.
2. The configured real MediaPipe Tasks model initializes.
3. Real video inference runs.
4. At least one frame contains valid pose landmarks.
5. The pose sequence is accepted by the real gait metrics pipeline.

If verification returns zero valid pose frames, choose another clearer side-view
clip or record a new walking video. Never treat model execution without real
landmarks as full verification.
