from typing import Literal
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from repository import chat_repository

from controller.auth_controller import current_auth
from domain.history import (
    InspectionAssignee,
    InspectionAssignmentRequest,
    InspectionAssignmentResponse,
    InspectionHistoryItem,
)
from service import history_service, inspection_service

router = APIRouter(prefix="/api/inspection", tags=["점검 이력"])


class InspectionNotesRequest(BaseModel):
    notes: str


@router.get("/histories", response_model=list[InspectionHistoryItem])
def get_recent_inspection_history(
    limit: int = Query(default=100, ge=1, le=1000),
    keyword: str | None = Query(default=None),
    location: str | None = Query(default=None),
    waste: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date: str | None = Query(default=None),
    auth=Depends(current_auth),
):
    return history_service.get_recent_history(
        user=auth[0],
        limit=limit,
        keyword=keyword,
        location=location,
        waste=waste,
        status=status,
        date=date,
    )


@router.get("/assignees", response_model=list[InspectionAssignee])
def get_inspection_assignees(_auth=Depends(current_auth)):
    return history_service.get_assignees()


@router.patch("/histories/{inspection_id}/assignee", response_model=InspectionAssignmentResponse)
def assign_inspection(
    inspection_id: int,
    payload: InspectionAssignmentRequest,
    auth=Depends(current_auth),
):
    return history_service.assign_history(inspection_id, payload.assigneeId, auth[0])


@router.get("/histories/{inspection_id}/image")
def get_inspection_image(
    inspection_id: int,
    kind: Literal["ORIGINAL", "ANNOTATED", "COLLECTION_PROOF"] | None = Query(default=None),
    auth=Depends(current_auth),
):
    stored_file, content_type = history_service.get_history_image(inspection_id, auth[0], kind)

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    return StreamingResponse(stream(), media_type=content_type)


@router.post("/histories/{inspection_id}/proof-image", status_code=status.HTTP_201_CREATED)
async def upload_proof_image(
    inspection_id: int,
    file: UploadFile = File(...),
    auth=Depends(current_auth),
):
    return await history_service.upload_proof_image(inspection_id, file, auth[0])


@router.delete("/histories/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspection_history(
    inspection_id: int,
    auth=Depends(current_auth),
):
    history_service.delete_history(inspection_id, auth[0])


@router.get("/histories/{inspection_id}", response_model=InspectionHistoryItem)
def get_inspection_history_detail(
    inspection_id: int,
    auth=Depends(current_auth),
):
    return history_service.get_history_detail(inspection_id, auth[0])


@router.patch("/histories/{inspection_id}/notes")
def update_inspection_notes(
    inspection_id: int,
    payload: InspectionNotesRequest,
    auth=Depends(current_auth),
):
    return history_service.update_notes(inspection_id, payload.notes, auth[0])


@router.patch("/histories/{inspection_id}/complete")
async def complete_inspection_history(
    inspection_id: int,
    afterImage: UploadFile = File(None),
    auth=Depends(current_auth),
):
    return await history_service.complete_history(inspection_id, afterImage, auth[0])


@router.post("/histories/{inspection_id}/analyze")
def analyze_inspection_image(
    inspection_id: int,
    auth=Depends(current_auth),
):
    return inspection_service.reanalyze_inspection(inspection_id, auth[0])


@router.get("/waste-types", response_model=list[str])
def get_waste_types():
    return chat_repository.find_waste_names()
