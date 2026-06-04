"""Application configuration.

Local development defaults to SQLite + local file storage. The structure is
PostgreSQL- and S3-ready: swap the `database_url` and implement an S3 storage
backend behind the same `StorageBackend` interface (see ``storage.py``).
"""
from __future__ import annotations

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

    # Demo presets force the simulated estimator with a known gait profile so the
    # product is demonstrable before heavy models are deployed.
    allow_demo_mode: bool = True

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

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

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.processed_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
