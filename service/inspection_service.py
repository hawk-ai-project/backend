# backend/service/inspection_service.py

import json

from fastapi import HTTPException, status

from domain.inspection import InspectionRequest, InspectionResponse
from repository import chat_repository, inspection_repository
from service import file_service

def analyze_image(payload: InspectionRequest) -> InspectionResponse:
# 터미널에 수신 확인 로그
    print(f"프론트엔드에서 사진 수신 완료, 데이터 길이 : {len(payload.image)}")

    # 추후 AI모델로 사진 분석하는 코드 입력

    # 분석 후 백엔드에서 프론트로 보낼 결과
    return InspectionResponse(
        message="사진을 전달받았습니다.",
        result="OK"
    )


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


def get_history_image(inspection_id: int, user: dict):
    return file_service.open_inspection_image(inspection_id, user)


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
