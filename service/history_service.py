from datetime import datetime
import hashlib
import io
import json
import uuid
from PIL import Image
from fastapi import HTTPException, UploadFile, status

# 1. chat_repository import 복구
from repository import chat_repository, history_repository
from service import file_service
from service.file_service import get_client, settings


def format_captured_at(captured_at) -> str:
    """'YYYY. M. D. HH:mm' 포맷으로 변환"""
    if not captured_at:
        return "-"
    if isinstance(captured_at, str):
        try:
            dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            return f"{dt.year}. {dt.month}. {dt.day}. {dt.strftime('%H:%M')}"
        except Exception:
            return captured_at
    if isinstance(captured_at, datetime):
        return f"{captured_at.year}. {captured_at.month}. {captured_at.day}. {captured_at.strftime('%H:%M')}"
    return str(captured_at)


def build_waste_summary(detections: list) -> str:
    """waste_types.name_ko와 count를 합산하여 '스티로폼 상자 2개' 형태 문자열 생성"""
    if not detections:
        return "탐지 결과 없음"

    counts = {}
    for d in detections:
        label = d.get("name_ko") or d.get("waste_type_name") or d.get("name") or "폐기물"
        cnt = int(d.get("count") or 1)
        counts[label] = counts.get(label, 0) + cnt

    summary_parts = [f"{label} {count}개" for label, count in counts.items() if label]
    return ", ".join(summary_parts) if summary_parts else "탐지 결과 없음"


def get_recent_history(
    user: dict,
    limit: int = 100,
    keyword: str | None = None,
    location: str | None = None,
    waste: str | None = None,
    status: str | None = None,
    date: str | None = None,
) -> list[dict]:
    clean_waste = None if waste in [None, "", "전체", "전체 폐기물"] else waste
    clean_status = None if status in [None, "", "전체", "전체 상태"] else status

    # 2. chat_repository를 이용한 기존 쿼리 호출 방식 복구
    rows = chat_repository.find_inspection_history(
        limit=limit,
        user_id=user["id"],
        is_admin=user.get("role") == "ADMIN",
    )

    result = []
    for row in rows:
        detections = row.get("detections") or []
        if isinstance(detections, str):
            try:
                detections = json.loads(detections)
            except Exception:
                detections = []

        inspection_id = row.get("id")
        image_id = row.get("imageId") or row.get("image_id")
        raw_status = row.get("status") or "PENDING"
        waste_summary = row.get("wasteSummary") or row.get("waste_summary") or build_waste_summary(detections)

        # 3. Pydantic schema 스펙에 맞춘 필드 구조 (status는 원본 영문 코드 유지)
        item = {
            "id": inspection_id,
            "title": row.get("title") or f"INSPECTION-{inspection_id}",
            "location": row.get("location") or row.get("title") or "위치 정보 없음",
            "coordinates": row.get("coordinates"),
            "capturedAt": row.get("capturedAt") or row.get("captured_at"),
            "status": raw_status,  # 한글 변환 없이 원본 영문 값 전달 (Pydantic 에러 방지)
            "priority": row.get("priority"),
            "notes": row.get("notes") or "",
            "aiOpinion": row.get("aiOpinion") or row.get("ai_opinion") or "",
            "inspectorName": row.get("inspectorName") or row.get("inspector_name") or "",
            "wasteSummary": waste_summary,
            "detections": detections,
            "imageId": image_id,
            "assigneeId": row.get("assigneeId") or row.get("assignee_id"),
            "assigneeName": row.get("assigneeName") or row.get("assignee_name") or "",
        }

        # 검색 필터링
        if keyword:
            kw = keyword.lower()
            if not (kw in item["title"].lower() or kw in item["notes"].lower() or kw in item["location"].lower()):
                continue

        if location and location.lower() not in item["location"].lower():
            continue

        if clean_waste and clean_waste.lower() not in item["wasteSummary"].lower():
            continue

        if clean_status and clean_status != item["status"]:
            continue

        if date and date not in str(item["capturedAt"] or ""):
            continue

        result.append(item)

    return result


def get_history_image(inspection_id: int, user: dict, kind: str | None = None):
    return file_service.open_inspection_image(inspection_id, user, kind)


def delete_history(inspection_id: int, user: dict) -> None:
    inspection = history_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="삭제할 수 있는 점검 이력을 찾을 수 없습니다.",
        )
    if not history_repository.soft_delete_inspection(inspection_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 삭제된 점검 이력입니다.",
        )


def get_assignees() -> list[dict]:
    return history_repository.find_active_assignees()


def assign_history(inspection_id: int, assignee_id: int, user: dict) -> dict:
    inspection = history_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="점검 이력을 찾을 수 없습니다.",
        )

    assignee = history_repository.find_active_user(assignee_id)
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="일반 사용자를 제외한 활성 계정만 담당자로 지정할 수 있습니다.",
        )

    history_repository.assign_inspection(inspection_id, assignee_id, user["id"])
    return {"inspectionId": inspection_id, "assignee": assignee, "status": "ACTION_REQUIRED"}


def update_notes(inspection_id: int, notes: str, user: dict) -> dict:
    inspection = history_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="점검 이력을 찾을 수 없습니다.",
        )

    history_repository.update_notes(inspection_id, notes)
    return {"inspectionId": inspection_id, "notes": notes}


def get_history_detail(inspection_id: int, user: dict) -> dict | None:
    is_admin = user.get("role") == "ADMIN"
    row = history_repository.find_inspection_detail(inspection_id, user["id"], is_admin)
    if not row:
        return None

    detections = row.get("detections") or []
    if isinstance(detections, str):
        try:
            detections = json.loads(detections)
        except Exception:
            detections = []

    waste_summary = (
        row.get("waste_summary")
        or row.get("wasteSummary")
        or build_waste_summary(detections)
    )

    return {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "location": row.get("location") or row.get("title") or "",
        "coordinates": row.get("coordinates"),
        "capturedAt": row.get("captured_at") or row.get("capturedAt"),
        "status": row.get("status") or "PENDING",
        "priority": row.get("priority") or "MEDIUM",
        "notes": row.get("notes") or "",
        "aiOpinion": row.get("ai_opinion") or row.get("aiOpinion") or "",
        "inspectorName": row.get("inspector_name") or row.get("inspectorName") or "",
        "wasteSummary": waste_summary,
        # "wasteSummary": row.get("waste_summary") or row.get("wasteSummary") or "",
        "detections": detections,
        "imageId": row.get("image_id") or row.get("imageId"),
        "assigneeId": row.get("assignee_id") or row.get("assigneeId"),
        "assigneeName": row.get("assignee_name") or row.get("assigneeName") or "",
    }


async def upload_proof_image(inspection_id: int, file: UploadFile, user: dict) -> dict:
    inspection = history_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="점검 이력을 찾을 수 없습니다.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일은 업로드할 수 없습니다.",
        )

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    width, height = None, None
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            width, height = img.size
    except Exception:
        pass

    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    storage_key = f"inspections/{inspection_id}/proof_{uuid.uuid4().hex}.{ext}"

    try:
        client = get_client()
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=storage_key,
            data=io.BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=file.content_type or "image/jpeg",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MinIO 업로드 실패: {str(e)}",
        )

    image_id = history_repository.insert_inspection_image(
        inspection_id=inspection_id,
        kind="COLLECTION_PROOF",
        storage_key=storage_key,
        original_name=file.filename,
        mime_type=file.content_type or "image/jpeg",
        byte_size=len(file_bytes),
        width=width,
        height=height,
        sha256=sha256_hash,
    )

    return {
        "imageId": image_id,
        "inspectionId": inspection_id,
        "kind": "COLLECTION_PROOF",
        "storageKey": storage_key,
    }