from fastapi import APIRouter, Depends, Query

from controller.admin_controller import current_admin
from domain.inspection import DetectionReviewRequest, MissedDetectionRequest
from service import ai_management_service


router = APIRouter(prefix="/api/admin/ai", tags=["AI Management"])


@router.get("/detections")
def detections(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    result: str | None = Query(None, pattern="^(UNREVIEWED|TRUE_POSITIVE|FALSE_POSITIVE|FALSE_NEGATIVE)$"),
    reviewStatus: str | None = Query(None, pattern="^(UNLABELED|LABELED|REVIEW_REQUIRED|REVIEWED|APPROVED|REJECTED)$"),
    className: str | None = Query(None, max_length=100),
    minConfidence: float | None = Query(None, ge=0, le=1),
    _admin=Depends(current_admin),
):
    return ai_management_service.list_detections(
        page, pageSize, keyword.strip() if keyword else None,
        result, reviewStatus, className, minConfidence,
    )


@router.patch("/detections/{detection_id}")
def review_detection(detection_id: int, payload: DetectionReviewRequest, admin=Depends(current_admin)):
    return ai_management_service.review_detection(detection_id, payload, admin["id"])


@router.post("/missed-detections", status_code=201)
def create_missed_detection(payload: MissedDetectionRequest, admin=Depends(current_admin)):
    return ai_management_service.create_missed(payload, admin["id"])


@router.get("/statistics")
def statistics(_admin=Depends(current_admin)):
    return ai_management_service.get_statistics()


@router.get("/classes")
def classes(_admin=Depends(current_admin)):
    return ai_management_service.get_classes()
