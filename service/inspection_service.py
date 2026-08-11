import json

from fastapi import HTTPException, status

from client import ai_client
from domain.inspection import InspectionCreateRequest, InspectionRequest, InspectionResponse
from repository import chat_repository, inspection_repository
from service import ai_error_service, file_service


def analyze_image(payload: InspectionRequest) -> InspectionResponse:
    try:
        result = ai_client.detect_image(payload.image)
        return InspectionResponse.model_validate(result)
    except ai_client.AIServerError as error:
        raise ai_error_service.to_http_exception(error) from error
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="AI 서버의 객체 탐지 응답 형식이 올바르지 않습니다.",
        ) from error


def get_recent_history(user: dict, limit: int) -> list[dict]:
    rows = chat_repository.find_inspection_history(
        limit=limit,
        user_id=user["id"],
        is_admin=user.get("role") == "ADMIN",
    )
    result = []
    for row in rows:
        detections = row.get("detections") or []
        if isinstance(detections, str):
            detections = json.loads(detections)
        result.append({
            "id": row["id"],
            "title": row["title"],
            "location": row["location"],
            "coordinates": row.get("coordinates"),
            "capturedAt": row["capturedAt"],
            "status": row["status"],
            "priority": row["priority"],
            "notes": row.get("notes"),
            "aiOpinion": row.get("aiOpinion"),
            "inspectorName": row["inspectorName"],
            "wasteSummary": row["wasteSummary"],
            "detections": detections,
            "imageId": row.get("imageId"),
            "assigneeId": row.get("assigneeId"),
            "assigneeName": row.get("assigneeName"),
        })
    return result


def create_inspection(payload: InspectionCreateRequest, user: dict) -> dict:
    try:
        analysis = ai_client.detect_image(payload.image)
    except ai_client.AIServerError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    original = file_service.store_inspection_data_image(payload.image, user["id"], "ORIGINAL")
    annotated_data = analysis.get("annotatedImage")
    annotated = None
    if isinstance(annotated_data, str) and annotated_data:
        annotated = file_service.store_inspection_data_image(annotated_data, user["id"], "ANNOTATED")

    location_id = inspection_repository.find_or_create_location(payload.location.strip(), user["id"])
    inspection_id = inspection_repository.create_inspection(
        location_id, user["id"], payload.title.strip(), payload.notes,
    )
    inspection_repository.create_inspection_image(inspection_id, "ORIGINAL", original)
    if annotated:
        inspection_repository.create_inspection_image(inspection_id, "ANNOTATED", annotated)
    return {
        "inspectionId": inspection_id,
        "message": "점검과 분석 이미지가 저장되었습니다.",
        "detections": analysis.get("detections") or [],
    }


def get_history_image(inspection_id: int, user: dict, kind: str | None = None):
    return file_service.open_inspection_image(inspection_id, user, kind)


def get_assignees() -> list[dict]:
    return inspection_repository.find_active_assignees()


def assign_history(inspection_id: int, assignee_id: int, user: dict) -> dict:
    inspection = inspection_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="점검 이력을 찾을 수 없습니다.")

    assignee = inspection_repository.find_active_user(assignee_id)
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="일반 사용자를 제외한 활성 계정만 담당자로 지정할 수 있습니다.",
        )

    inspection_repository.assign_inspection(inspection_id, assignee_id, user["id"])
    return {"inspectionId": inspection_id, "assignee": assignee}
