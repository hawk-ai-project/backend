# backend/controller/inspection_controller.py

from fastapi import APIRouter, Depends
from controller.auth_controller import current_auth
from domain.inspection import (
    InspectionCreateRequest, InspectionCreateResponse,
    InspectionRequest, InspectionResponse, InspectionSaveRequest
)
from service import inspection_service

router = APIRouter(prefix="/api/inspection", tags=["현장점검"])

@router.post("", response_model=InspectionCreateResponse)
def create_inspection(payload: InspectionCreateRequest, auth=Depends(current_auth)):
    return inspection_service.create_inspection(payload, auth[0])

@router.post("/analyze", response_model=InspectionResponse)
def analyze_inspection_image(payload: InspectionRequest):
    return inspection_service.analyze_image(payload)

@router.post("/save")
def save_inspection_record(
    payload: InspectionSaveRequest,
    auth=Depends(current_auth),
):
    return inspection_service.save_inspection(payload, auth[0])

# 분석 버튼 누를 시
@router.post("/histories/{inspection_id}/analyze")
def analyze_existing_inspection(inspection_id: int, auth=Depends(current_auth)):
    return inspection_service.reanalyze_inspection(inspection_id, auth[0])