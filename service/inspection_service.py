# backend/service/inspection_service.py

import json

from domain.inspection import InspectionRequest, InspectionResponse
from repository import chat_repository
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
        })
    return result


def get_history_image(inspection_id: int, user: dict):
    return file_service.open_inspection_image(inspection_id, user)
