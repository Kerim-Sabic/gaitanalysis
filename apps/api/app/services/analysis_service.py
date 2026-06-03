"""Async analysis job runner.

Local implementation uses a bounded ``ThreadPoolExecutor`` and persists progress
to storage so the API can poll (or push over WebSocket). The ``submit`` interface
is deliberately queue-shaped so a Celery/RQ broker can replace the executor
without changing callers.
"""
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.pipeline.orchestrator import STAGES, AnalysisError, GaitPipeline
from app.schemas import (
    AnalysisProgress,
    AnalysisStageState,
    AnalysisStatus,
    PatientCase,
    ReviewStatus,
    TestType,
    VideoMetadata,
)
from app.storage import Storage


def _initial_stages() -> list[AnalysisStageState]:
    stages = [AnalysisStageState(key="upload", label="Upload received", status="done")]
    stages += [AnalysisStageState(key=k, label=lbl) for k, lbl in STAGES]
    return stages


class AnalysisService:
    def __init__(self, storage: Storage, max_workers: int = 2):
        self.storage = storage
        self.pipeline = GaitPipeline()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def create_job(self, case_id: str) -> AnalysisProgress:
        import uuid

        progress = AnalysisProgress(
            analysis_id=f"analysis_{uuid.uuid4().hex[:10]}",
            case_id=case_id,
            status=AnalysisStatus.queued,
            progress=0.0,
            stages=_initial_stages(),
        )
        self.storage.create_analysis(progress)
        return progress

    def submit(
        self,
        progress: AnalysisProgress,
        case: PatientCase,
        video: VideoMetadata,
        test_type: TestType,
        demo_preset: str | None = None,
    ) -> None:
        self.executor.submit(self._run, progress, case, video, test_type, demo_preset)

    # ------------------------------------------------------------------ #
    def _run(self, progress, case, video, test_type, demo_preset):
        progress.status = AnalysisStatus.running
        self._touch(progress)

        def on_progress(stage_key: str, frac: float):
            for s in progress.stages:
                if s.key == stage_key:
                    s.status = "done"
                elif s.status == "pending":
                    s.status = "active"
                    break
            # mark everything up to current as done, current active
            self._mark(progress, stage_key)
            progress.progress = round(frac, 3)
            progress.current_stage = stage_key
            self._touch(progress)

        try:
            output = self.pipeline.run(
                analysis_id=progress.analysis_id,
                case=case,
                video=video,
                test_type=test_type,
                demo_preset=demo_preset,
                progress=on_progress,
            )
            self.storage.save_result(output.result)
            self.storage.save_pose(output.pose_track)
            # Demo runs may have produced a playable clip; persist the updated path.
            self.storage.update_video(video)

            # Link back onto the case.
            case.last_analysis_at = datetime.now(timezone.utc)
            case.last_analysis_id = progress.analysis_id
            case.review_status = ReviewStatus.pending
            self.storage.update_case(case)

            for s in progress.stages:
                s.status = "done"
            progress.status = AnalysisStatus.completed
            progress.progress = 1.0
            progress.current_stage = None
            self._touch(progress)
        except AnalysisError as e:
            self._fail(progress, str(e), e.code)
        except Exception as e:  # pragma: no cover - defensive
            self._fail(progress, f"Unexpected error: {e}", "analysis_failed")
            traceback.print_exc()

    def _mark(self, progress, current_key):
        order = [s.key for s in progress.stages]
        ci = order.index(current_key) if current_key in order else -1
        for i, s in enumerate(progress.stages):
            if i < ci:
                s.status = "done"
            elif i == ci:
                s.status = "active"

    def _fail(self, progress, message, code):
        progress.status = AnalysisStatus.failed
        progress.error = message
        for s in progress.stages:
            if s.status == "active":
                s.status = "error"
        self._touch(progress)

    def _touch(self, progress):
        progress.updated_at = datetime.now(timezone.utc)
        self.storage.update_progress(progress)


_service: AnalysisService | None = None


def get_analysis_service() -> AnalysisService:
    global _service
    if _service is None:
        from app.storage import get_storage

        _service = AnalysisService(get_storage())
    return _service
