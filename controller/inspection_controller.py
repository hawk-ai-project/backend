# 현장점검 컨트롤러 (backend/controller/inspection_controller.py)


from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from controller.auth_controller import current_auth
from domain.inspection import (
    InspectionAssignee, InspectionAssignmentRequest, InspectionAssignmentResponse,
    InspectionCreateRequest, InspectionCreateResponse,
    InspectionHistoryItem, InspectionRequest, InspectionResponse, InspectionSaveRequest
)
from service import inspection_service

router = APIRouter(prefix="/api/inspection", tags=["현장점검"])


@router.post("", response_model=InspectionCreateResponse)
def create_inspection(payload: InspectionCreateRequest, auth=Depends(current_auth)):
    return inspection_service.create_inspection(payload, auth[0])


@router.get("/histories", response_model=list[InspectionHistoryItem])
def get_recent_inspection_history(
    limit: int = Query(default=100, ge=1, le=1000),
    auth=Depends(current_auth),
):
    return inspection_service.get_recent_history(auth[0], limit)


@router.get("/assignees", response_model=list[InspectionAssignee])
def get_inspection_assignees(_auth=Depends(current_auth)):
    return inspection_service.get_assignees()


@router.patch("/histories/{inspection_id}/assignee", response_model=InspectionAssignmentResponse)
def assign_inspection(
    inspection_id: int,
    payload: InspectionAssignmentRequest,
    auth=Depends(current_auth),
):
    return inspection_service.assign_history(inspection_id, payload.assigneeId, auth[0])


@router.get("/histories/{inspection_id}/image")
def get_inspection_image(
    inspection_id: int,
    kind: Literal["ORIGINAL", "ANNOTATED"] | None = Query(default=None),
    auth=Depends(current_auth),
):
    stored_file, content_type = inspection_service.get_history_image(inspection_id, auth[0], kind)

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    return StreamingResponse(stream(), media_type=content_type)


@router.post("/analyze", response_model=InspectionResponse)
def analyze_inspection_image(payload: InspectionRequest):
    return inspection_service.analyze_image(payload)


@router.post("/save")
def save_inspection_record(
    payload: InspectionSaveRequest,
    auth=Depends(current_auth),
):
    return inspection_service.save_inspection(payload, auth[0])