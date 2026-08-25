# backend/controller/inspection_controller.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from controller.auth_controller import current_auth
from domain.inspection import (
    InspectionCreateRequest, InspectionCreateResponse,
    InspectionRequest, InspectionResponse, InspectionSaveRequest
)
from service import inspection_service

router = APIRouter(prefix="/api/inspection", tags=["현장점검"])


class ReinspectionApproveRequest(BaseModel):
    inspectionIds: list[int] = Field(min_length=1, max_length=200)


class ReinspectionBox(BaseModel):
    id: int | None = None
    className: str = Field(min_length=1, max_length=100)
    bbox: list[float] = Field(min_length=4, max_length=4)


class ReinspectionAnnotationRequest(BaseModel):
    boxes: list[ReinspectionBox] = Field(default_factory=list, max_length=500)
    deletedIds: list[int] = Field(default_factory=list, max_length=500)


class ReinspectionModelSelectRequest(BaseModel):
    modelId: str = Field(min_length=1, max_length=255)

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
@router.get("/reinspection-targets")
def reinspection_targets(auth=Depends(current_auth)):
    return inspection_service.get_reinspection_targets(auth[0])


@router.patch("/reinspection-targets/approve")
def approve_reinspection_targets(payload: ReinspectionApproveRequest, auth=Depends(current_auth)):
    return inspection_service.approve_reinspection_targets(payload.inspectionIds, auth[0])


@router.get("/reinspection-targets/classes")
def reinspection_classes(_auth=Depends(current_auth)):
    return inspection_service.get_reinspection_classes()


@router.get("/reinspection-targets/models")
def reinspection_models(auth=Depends(current_auth)):
    return inspection_service.get_reinspection_models(auth[0])


@router.post("/reinspection-targets/{inspection_id}/model/select")
def select_reinspection_model(inspection_id: int, payload: ReinspectionModelSelectRequest, auth=Depends(current_auth)):
    return inspection_service.select_reinspection_model(inspection_id, payload.modelId, auth[0])



@router.get("/reinspection-targets/{inspection_id}/model")
def reinspection_model_detail(inspection_id: int, auth=Depends(current_auth)):
    return inspection_service.get_reinspection_model_detail(inspection_id, auth[0])


@router.get("/reinspection-targets/{inspection_id}/model/artifacts/{artifact:path}")
def reinspection_model_artifact(inspection_id: int, artifact: str, auth=Depends(current_auth)):
    content, content_type = inspection_service.get_reinspection_model_artifact(inspection_id, artifact, auth[0])
    return StreamingResponse(iter([content]), media_type=content_type)
@router.get("/reinspection-targets/{inspection_id}")
def reinspection_detail(inspection_id: int, auth=Depends(current_auth)):
    return inspection_service.get_reinspection_detail(inspection_id, auth[0])


@router.put("/reinspection-targets/{inspection_id}/annotations")
def save_reinspection_annotations(inspection_id: int, payload: ReinspectionAnnotationRequest, auth=Depends(current_auth)):
    return inspection_service.save_reinspection_annotations(inspection_id, payload, auth[0])
