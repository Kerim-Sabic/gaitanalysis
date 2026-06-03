# Sample videos

Place a real walking clip here for full model verification:

```
data/sample_videos/walk_test.mp4
```

Then run:

```
python scripts/test_pose_on_sample_video.py
```

If no file is present, the test script generates a simple synthetic clip. A
generated clip only verifies that the model **executes** — it does **not**
verify clinical gait performance. Use a real side-view walking video for a
meaningful keypoint test.
