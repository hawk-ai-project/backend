import json

from fastapi import HTTPException

from client import ai_client
from domain.inspection import InspectionRequest, InspectionResponse
from repository import chat_repository
from service import file_service


def analyze_image(payload: InspectionRequest) -> InspectionResponse:
    try:
        result = ai_client.detect_image(payload.image)
        return InspectionResponse.model_validate(result)
    except ai_client.AIServerError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=f"AI 서버의 객체 탐지 응답 형식이 올바르지 않습니다: {error}",
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
        })
    return result


def get_history_image(inspection_id: int, user: dict):
    return file_service.open_inspection_image(inspection_id, user)
