# 현장점검 컨트롤러 (backend/controller/inspection_controller.py)


from fastapi import APIRouter

from domain.inspection import InspectionRequest, InspectionResponse
from service import inspection_service

router = APIRouter(prefix="/api/inspection", tags=["현장점검"])

@router.post("/analyze", response_model=InspectionResponse)
def analyze_inspection_image(payload: InspectionRequest):
    return inspection_service.analyze_image(payload)