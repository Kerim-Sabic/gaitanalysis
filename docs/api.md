# API Reference

Base URL (dev): `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.
The web app reaches these through the Next rewrite at `/api/*`.

All payloads are JSON unless noted. Schemas are defined in
`apps/api/app/schemas.py` and mirrored in `packages/shared`.

## Meta
| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Service info + disclaimer |
| GET | `/health` | Health + which pose models are installed |

## Cases
| Method | Path | Description |
| --- | --- | --- |
| POST | `/cases` | Create a de-identified case. Body: `PatientCaseCreate`. |
| GET | `/cases` | List cases with last-analysis summary. |
| GET | `/cases/{case_id}` | Get a case. |
| PATCH | `/cases/{case_id}/review` | Update review status (`pending`/`in_review`/`reviewed`). |

## Videos
| Method | Path | Description |
| --- | --- | --- |
| POST | `/videos/upload` | Multipart: `case_id`, `test_type`, `camera_view`, `calibration_distance_m?`, `file`. Returns `VideoMetadata`. |
| GET | `/videos/{video_id}` | Video metadata. |
| GET | `/videos/{video_id}/quality` | Pre-analysis (frame-based) quality check → `QualityResult`. |
| GET | `/videos/{video_id}/raw` | Stream the stored video. |
| DELETE | `/videos/{video_id}` | Delete the stored video file (privacy). |

## Analysis
| Method | Path | Description |
| --- | --- | --- |
| POST | `/analysis/start` | Body: `{ video_id, test_type?, demo_preset? }`. Returns `AnalysisProgress` (job queued). |
| POST | `/analysis/demo` | Body: `{ preset }` (`normal`/`asymmetric`/`poor_quality`/`tug`). Creates a demo case + virtual video and runs the real pipeline on simulated keypoints. |
| GET | `/analysis/{id}/status` | Poll job progress (`AnalysisProgress`). |
| GET | `/analysis/{id}/result` | Full `GaitAnalysisResult` (409 while running). |
| GET | `/analysis/{id}/pose` | `PoseTrack` for the overlay (keypoints/frame). |
| GET | `/analysis/{id}/report.json` | Structured JSON report. |
| GET | `/analysis/{id}/report.pdf` | Clinician PDF report. |
| GET | `/analysis/{id}/overlay-video` | Rendered skeleton overlay MP4 (lazy-generated). |

## Error codes
`415` unsupported file type · `413` file too large · `400` invalid/short video ·
`404` not found · `409` analysis still running · `500` rendering failed.
Analysis-job failures are reported in `AnalysisProgress.error` with a `code`
(`video_invalid`, `no_person`, `multiple_people`, `analysis_failed`).

## Example result (abridged)

```json
{
  "analysis_id": "analysis_001",
  "status": "completed",
  "test_type": "standard_walk",
  "analysis_mode": "clinical",
  "quality": { "overall_score": 86, "feet_visibility": 88, "warnings": [] },
  "metrics": [
    { "key": "cadence_steps_per_min", "label": "Cadence", "value": 104,
      "unit": "steps/min", "confidence": 0.91, "status": "good",
      "interpretation": "Within expected range (context dependent)." }
  ],
  "asymmetry": [
    { "key": "step_time_asymmetry", "label": "Step time",
      "asymmetry_percent": 8.4, "status": "review",
      "interpretation": "Mild asymmetry — clinician review recommended." }
  ],
  "clinical_flags": [
    { "name": "Mild temporal step asymmetry", "severity": "low",
      "confidence": 0.84, "explanation": "Left/right step timing differs ..." }
  ],
  "mobility_risk_support_score": 22.0,
  "mobility_risk_band": "low",
  "limitations": ["Single-camera 2D analysis limits depth accuracy."],
  "report_summary": "AI-assisted gait quantification ... for clinician review."
}
```
