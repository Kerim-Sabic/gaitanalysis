"""Persistence layer.

Local-first: SQLite for records + JSON files for large artefacts (results, pose
tracks). The public methods form a repository interface that can be backed by
PostgreSQL + S3 later without changing callers.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.schemas import (
    AnalysisProgress,
    AnalysisStageState,
    AnalysisStatus,
    GaitAnalysisResult,
    PatientCase,
    PoseTrack,
    VideoMetadata,
)


class Storage:
    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self.db_path = Path(db_path) if db_path else (settings.data_dir / "horalix.db")
        self.processed = settings.processed_dir
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY, case_id TEXT, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, case_id TEXT, video_id TEXT,
                    progress TEXT NOT NULL, result_path TEXT, pose_path TEXT,
                    created_at TEXT
                );
                """
            )
            self._conn.commit()

    # ----------------------------- cases ----------------------------- #
    def create_case(self, case: PatientCase) -> PatientCase:
        with self._lock:
            self._conn.execute(
                "INSERT INTO cases (id, data, created_at) VALUES (?,?,?)",
                (case.id, case.model_dump_json(), case.created_at.isoformat()),
            )
            self._conn.commit()
        return case

    def get_case(self, case_id: str) -> Optional[PatientCase]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM cases WHERE id=?", (case_id,)
            ).fetchone()
        return PatientCase.model_validate_json(row["data"]) if row else None

    def list_cases(self) -> list[PatientCase]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM cases ORDER BY created_at DESC"
            ).fetchall()
        return [PatientCase.model_validate_json(r["data"]) for r in rows]

    def update_case(self, case: PatientCase) -> PatientCase:
        with self._lock:
            self._conn.execute(
                "UPDATE cases SET data=? WHERE id=?", (case.model_dump_json(), case.id)
            )
            self._conn.commit()
        return case

    # ----------------------------- videos ---------------------------- #
    def create_video(self, video: VideoMetadata) -> VideoMetadata:
        with self._lock:
            self._conn.execute(
                "INSERT INTO videos (id, case_id, data) VALUES (?,?,?)",
                (video.id, video.case_id, video.model_dump_json()),
            )
            self._conn.commit()
        return video

    def get_video(self, video_id: str) -> Optional[VideoMetadata]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM videos WHERE id=?", (video_id,)
            ).fetchone()
        return VideoMetadata.model_validate_json(row["data"]) if row else None

    def update_video(self, video: VideoMetadata) -> VideoMetadata:
        with self._lock:
            self._conn.execute(
                "UPDATE videos SET data=? WHERE id=?", (video.model_dump_json(), video.id)
            )
            self._conn.commit()
        return video

    # --------------------------- analyses ---------------------------- #
    def create_analysis(self, progress: AnalysisProgress) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO analyses (id, case_id, video_id, progress, created_at) "
                "VALUES (?,?,?,?,?)",
                (progress.analysis_id, progress.case_id, None,
                 progress.model_dump_json(), progress.updated_at.isoformat()),
            )
            self._conn.commit()

    def update_progress(self, progress: AnalysisProgress) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE analyses SET progress=? WHERE id=?",
                (progress.model_dump_json(), progress.analysis_id),
            )
            self._conn.commit()

    def get_progress(self, analysis_id: str) -> Optional[AnalysisProgress]:
        with self._lock:
            row = self._conn.execute(
                "SELECT progress FROM analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        return AnalysisProgress.model_validate_json(row["progress"]) if row else None

    def save_result(self, result: GaitAnalysisResult) -> None:
        path = self.processed / f"{result.analysis_id}_result.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        with self._lock:
            self._conn.execute(
                "UPDATE analyses SET result_path=?, video_id=? WHERE id=?",
                (str(path), result.video_id, result.analysis_id),
            )
            self._conn.commit()

    def get_result(self, analysis_id: str) -> Optional[GaitAnalysisResult]:
        with self._lock:
            row = self._conn.execute(
                "SELECT result_path FROM analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        if not row or not row["result_path"]:
            return None
        p = Path(row["result_path"])
        if not p.exists():
            return None
        return GaitAnalysisResult.model_validate_json(p.read_text(encoding="utf-8"))

    def save_pose(self, pose: PoseTrack) -> None:
        path = self.processed / f"{pose.analysis_id}_pose.json"
        path.write_text(pose.model_dump_json(), encoding="utf-8")
        with self._lock:
            self._conn.execute(
                "UPDATE analyses SET pose_path=? WHERE id=?", (str(path), pose.analysis_id)
            )
            self._conn.commit()

    def get_pose(self, analysis_id: str) -> Optional[PoseTrack]:
        with self._lock:
            row = self._conn.execute(
                "SELECT pose_path FROM analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        if not row or not row["pose_path"]:
            return None
        p = Path(row["pose_path"])
        return PoseTrack.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


_storage: Optional[Storage] = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
