"""Patient case endpoints. Cases are de-identified by design (codes/initials)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas import PatientCase, PatientCaseCreate, ReviewStatus
from app.storage import get_storage

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseSummary(BaseModel):
    case: PatientCase
    last_risk_band: str | None = None
    last_quality: float | None = None
    last_mode: str | None = None


@router.post("", response_model=PatientCase)
def create_case(payload: PatientCaseCreate) -> PatientCase:
    case = PatientCase(id=f"case_{uuid.uuid4().hex[:10]}", **payload.model_dump())
    return get_storage().create_case(case)


@router.get("", response_model=list[CaseSummary])
def list_cases() -> list[CaseSummary]:
    storage = get_storage()
    out: list[CaseSummary] = []
    for case in storage.list_cases():
        summary = CaseSummary(case=case)
        if case.last_analysis_id:
            res = storage.get_result(case.last_analysis_id)
            if res:
                summary.last_risk_band = res.mobility_risk_band
                summary.last_quality = res.quality.overall_score
                summary.last_mode = res.analysis_mode.value
        out.append(summary)
    return out


@router.get("/{case_id}", response_model=PatientCase)
def get_case(case_id: str) -> PatientCase:
    case = get_storage().get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


class ReviewUpdate(BaseModel):
    review_status: ReviewStatus


@router.patch("/{case_id}/review", response_model=PatientCase)
def update_review(case_id: str, payload: ReviewUpdate) -> PatientCase:
    storage = get_storage()
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    case.review_status = payload.review_status
    return storage.update_case(case)
