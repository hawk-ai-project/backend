from fastapi import APIRouter, Depends, Query, Response, status

from controller.admin_controller import current_admin
from domain.inspection import DataBulkActionRequest, DataTagCreateRequest, DetectionReviewRequest, MissedDetectionRequest
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


@router.get("/models")
def models(_admin=Depends(current_admin)):
    return ai_management_service.get_models()


@router.post("/models/{model_id:path}/select")
def select_model(model_id: str, _admin=Depends(current_admin)):
    return ai_management_service.select_model(model_id)


@router.get("/system")
def system(_admin=Depends(current_admin)):
    return ai_management_service.get_system()


@router.get("/classes")
def classes(_admin=Depends(current_admin)):
    return ai_management_service.get_classes()


@router.get("/data")
def data_browser(
    page:int=Query(1,ge=1),pageSize:int=Query(24,ge=1,le=100),
    keyword:str|None=Query(None,max_length=100),className:str|None=Query(None,max_length=100),
    tagIds:list[int]=Query(default=[]),result:str|None=Query(None),
    reviewStatus:str|None=Query(None),retraining:bool|None=Query(None),
    _admin=Depends(current_admin),
):
    return ai_management_service.browse_data(page,pageSize,keyword,className,tagIds,result,reviewStatus,retraining)


@router.get("/tags")
def tags(_admin=Depends(current_admin)):
    return ai_management_service.get_tags()


@router.post("/tags",status_code=201)
def create_tag(payload:DataTagCreateRequest,admin=Depends(current_admin)):
    return ai_management_service.create_tag(payload,admin["id"])


@router.post("/data/bulk")
def bulk_data(payload:DataBulkActionRequest,admin=Depends(current_admin)):
    return ai_management_service.bulk_action(payload,admin["id"])


@router.get("/data/{inspection_id}")
def data_detail(inspection_id:int,_admin=Depends(current_admin)):
    return ai_management_service.get_data_detail(inspection_id)


@router.delete("/detections/{detection_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_detection(detection_id:int,_admin=Depends(current_admin)):
    ai_management_service.delete_annotation(detection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
