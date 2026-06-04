"""Application configuration.

Local development defaults to SQLite + local file storage. The structure is
PostgreSQL- and S3-ready: swap the `database_url` and implement an S3 storage
backend behind the same `StorageBackend` interface (see ``storage.py``).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: apps/api/app/config.py -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HORALIX_", env_file=".env", extra="ignore")

    app_name: str = "Horalix Gait AI"
    version: str = "0.1.0"

    # Storage (local-first; S3-compatible abstraction lives in storage.py)
    data_dir: Path = REPO_ROOT / "data"
    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'horalix.db').as_posix()}"

    # Pose backend preference (env: HORALIX_POSE_BACKEND).
    # Supported: auto_best, mediapipe_tasks_full, mediapipe_tasks_heavy,
    # mmpose_rtmw, mmpose_rtmw3d, ultralytics_pose, demo.
    # Real analysis NEVER silently falls back to demo — if the configured real
    # backend is unavailable it fails clearly; demo can be selected explicitly.
    pose_backend: str = "auto_best"

    # Auto-best selection mode (env: HORALIX_AUTO_BEST_MODE).
    #   "fast" (default): run only the single preferred available backend — fast
    #          uploads, no redundant multi-backend inference.
    #   "full": run every available backend and pick the measured best (used by
    #          sample selection / verification).
    auto_best_mode: str = "fast"

    # Live (near-real-time) preview backend — lighter model for low latency.
    # The recorded clip is still analysed by `final_backend` for the report.
    live_backend: str = "mediapipe_tasks_full"
    final_backend: str = "auto_best"
    live_min_detection_confidence: float = 0.4

    # Frame budget for analysis (perf). 0 = use library defaults.
    # max_analysis_frames caps total analysed frames; frame_stride forces an
    # additional temporal subsample; analysis_fps_target is informational.
    max_analysis_frames: int = 900
    frame_stride: int = 0
    analysis_fps_target: float = 0.0

    # Demo presets force the simulated estimator with a known gait profile so the
    # product is demonstrable before heavy models are deployed.
    allow_demo_mode: bool = True

    # CORS. Accepts comma-separated origins (recommended) or a JSON list.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Analysis constraints
    min_video_seconds: float = 2.0
    max_video_seconds: float = 600.0
    min_fps: float = 12.0

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw.startswith("["):
            try:
                values = json.loads(raw)
            except json.JSONDecodeError:
                values = []
        else:
            values = raw.split(",")
        return [str(origin).strip().rstrip("/") for origin in values if str(origin).strip()]

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.processed_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
