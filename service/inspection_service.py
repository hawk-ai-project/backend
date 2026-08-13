import json

from fastapi import HTTPException, status

from client import ai_client
from domain.inspection import InspectionCreateRequest, InspectionRequest, InspectionResponse, InspectionSaveRequest
from repository import chat_repository, inspection_repository
from service import ai_error_service, file_service, geocoding_service


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
    return _create_inspection_with_image(payload, user)


def _create_inspection_with_image(
    payload: InspectionCreateRequest,
    user: dict,
    *,
    status: str = "REVIEW_REQUIRED",
) -> dict:
    analysis_unavailable = False
    try:
        analysis = ai_client.detect_image(payload.image)
    except ai_client.AIServerError as error:
        # Do not discard a field inspection just because AI is temporarily down.
        analysis = {"detections": []}
        analysis_unavailable = True

    original = file_service.store_inspection_data_image(payload.image, user["id"], "ORIGINAL")
    annotated_data = analysis.get("annotatedImage")
    annotated = None
    if isinstance(annotated_data, str) and annotated_data:
        annotated = file_service.store_inspection_data_image(annotated_data, user["id"], "ANNOTATED")

    latitude, longitude = payload.latitude, payload.longitude
    if latitude is None or longitude is None:
        resolved = geocoding_service.geocode(payload.location)
        if resolved:
            latitude, longitude = resolved
    location_id = inspection_repository.find_or_create_location(
        payload.location.strip(), user["id"], latitude, longitude,
    )
    inspection_id = inspection_repository.create_inspection(
        location_id,
        user["id"],
        payload.title.strip(),
        payload.notes,
        "DRAFT" if analysis_unavailable else status,
    )
    original_image_id = inspection_repository.create_inspection_image(inspection_id, "ORIGINAL", original)
    annotated_image_id = None
    if annotated:
        annotated_image_id = inspection_repository.create_inspection_image(inspection_id, "ANNOTATED", annotated)
    if not analysis_unavailable:
        inspection_repository.save_detection_result(
            inspection_id, original_image_id, annotated_image_id, analysis,
        )
    return {
        "inspectionId": inspection_id,
        "message": "점검과 분석 이미지가 저장되었습니다.",
        "detections": analysis.get("detections") or [],
    }


def get_history_image(inspection_id: int, user: dict, kind: str | None = None):
    return file_service.open_inspection_image(inspection_id, user, kind)


def delete_history(inspection_id: int, user: dict) -> None:
    inspection = inspection_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="삭제할 수 있는 점검 이력을 찾을 수 없습니다.",
        )
    if not inspection_repository.soft_delete_inspection(inspection_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 삭제된 점검 이력입니다.",
        )


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


def _parse_legacy_coordinates(coordinates: str) -> tuple[float | None, float | None]:
    try:
        latitude, longitude = (float(value.strip()) for value in coordinates.split(",", 1))
    except (AttributeError, TypeError, ValueError):
        return None, None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None, None
    return latitude, longitude


def save_inspection(payload: InspectionSaveRequest, user: dict) -> dict:
    latitude, longitude = _parse_legacy_coordinates(payload.coordinates)
    request = InspectionCreateRequest(
        image=payload.image,
        title=payload.title,
        location=payload.location_name,
        notes=payload.notes,
        latitude=latitude,
        longitude=longitude,
    )
    return _create_inspection_with_image(request, user, status=payload.status)

    # AI 분석 결과 요약
    if payload.ai_detections:
        ai_opinion = ", ".join([f"{d.className} {int(d.confidence * 100)}%" for d in payload.ai_detections])
    else:
        ai_opinion = "발견된 객체 없음"

    # 2. DB 저장소 호출
    inspection_repository.insert_inspection_record(payload, user["id"], ai_opinion)
    
    return {"message": "현장 점검 이력이 성공적으로 저장되었습니다."}
