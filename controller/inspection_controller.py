# backend/controller/inspection_controller.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from controller.auth_controller import current_auth
from domain.inspection import (
    InspectionCreateRequest,
    InspectionCreateResponse,
    InspectionRequest,
    InspectionResponse,
    InspectionSaveRequest,
)
from service import inspection_service
from common.weather import fetch_realtime_weather

router = APIRouter(prefix="/api/inspection", tags=["현장점검"])


# ==============================================================================
# 1. 재점검 전용 DTO 스키마
# ==============================================================================


# 재점검 대상 건 일괄 승인 요청
class ReinspectionApproveRequest(BaseModel):
    inspectionIds: list[int] = Field(min_length=1, max_length=200)


# 재점검 단일 바운딩 박스 라벨링 데이터
class ReinspectionBox(BaseModel):
    id: int | None = None
    className: str = Field(min_length=1, max_length=100)
    bbox: list[float] = Field(min_length=4, max_length=4)


# 재점검 어노테이션 저장 요청 (수정/신규 박스 목록 및 삭제 대상 ID 목록)
class ReinspectionAnnotationRequest(BaseModel):
    boxes: list[ReinspectionBox] = Field(default_factory=list, max_length=500)
    deletedIds: list[int] = Field(default_factory=list, max_length=500)


# 재점검 시 적용할 AI 모델 선택 요청
class ReinspectionModelSelectRequest(BaseModel):
    modelId: str = Field(min_length=1, max_length=255)


# ==============================================================================
# 2. 현장 점검 기본 API (생성 / 실시간 분석 / 최종 저장)
# ==============================================================================


# 신규 현장 점검 건 생성
@router.post("", response_model=InspectionCreateResponse)
def create_inspection(payload: InspectionCreateRequest, auth=Depends(current_auth)):
    coords = getattr(payload, "coordinates", None) or ""
    weather_info = fetch_realtime_weather(coords) if coords else None
    return inspection_service.create_inspection(
        payload, auth[0], weather_info=weather_info
    )


# 업로드 이미지 실시간 AI 객체 탐지 분석
@router.post("/analyze", response_model=InspectionResponse)
def analyze_inspection_image(payload: InspectionRequest):
    return inspection_service.analyze_image(payload)


# 현장 점검 정보 및 탐지 결과 최종 저장
@router.post("/save")
def save_inspection_record(
    payload: InspectionSaveRequest,
    auth=Depends(current_auth),
):
    # 프론트엔드(InspectionInfo.jsx)에서 전달된 좌표 기반 실시간 기상청 초단기실황 수집
    weather_info = fetch_realtime_weather(payload.coordinates or "")
    return inspection_service.save_inspection(
        payload, auth[0], weather_info=weather_info
    )


# ==============================================================================
# 3. 재점검(Re-inspection) 및 AI 모델 관리 API
# ==============================================================================


# 재점검 대상(DRAFT 상태) 목록 조회
@router.get("/reinspection-targets")
def reinspection_targets(auth=Depends(current_auth)):
    return inspection_service.get_reinspection_targets(auth[0])


# 재점검 대상 건 일괄 승인 처리 (REVIEW_REQUIRED 전환)
@router.patch("/reinspection-targets/approve")
def approve_reinspection_targets(
    payload: ReinspectionApproveRequest, auth=Depends(current_auth)
):
    return inspection_service.approve_reinspection_targets(
        payload.inspectionIds, auth[0]
    )


# 재점검 라벨링용 활성 폐기물 분류 클래스 목록 조회
@router.get("/reinspection-targets/classes")
def reinspection_classes(_auth=Depends(current_auth)):
    return inspection_service.get_reinspection_classes()


# 재점검 시 사용 가능한 AI 모델 목록 조회
@router.get("/reinspection-targets/models")
def reinspection_models(auth=Depends(current_auth)):
    return inspection_service.get_reinspection_models(auth[0])


# 특정 점검 건에 적용할 AI 모델 변경/선택
@router.post("/reinspection-targets/{inspection_id}/model/select")
def select_reinspection_model(
    inspection_id: int,
    payload: ReinspectionModelSelectRequest,
    auth=Depends(current_auth),
):
    return inspection_service.select_reinspection_model(
        inspection_id, payload.modelId, auth[0]
    )


# 특정 점검 건에 적용된 AI 모델 상세 메타데이터 및 성능 지표 조회
@router.get("/reinspection-targets/{inspection_id}/model")
def reinspection_model_detail(inspection_id: int, auth=Depends(current_auth)):
    return inspection_service.get_reinspection_model_detail(inspection_id, auth[0])


# AI 모델 관련 아티팩트 파일 스트리밍 다운로드 (가중치, 혼동 행렬 등)
@router.get("/reinspection-targets/{inspection_id}/model/artifacts/{artifact:path}")
def reinspection_model_artifact(
    inspection_id: int, artifact: str, auth=Depends(current_auth)
):
    content, content_type = inspection_service.get_reinspection_model_artifact(
        inspection_id, artifact, auth[0]
    )
    return StreamingResponse(iter([content]), media_type=content_type)


# 특정 재점검 건 단건 상세 조회 (바운딩 박스 및 모델 정보 포함)
@router.get("/reinspection-targets/{inspection_id}")
def reinspection_detail(inspection_id: int, auth=Depends(current_auth)):
    return inspection_service.get_reinspection_detail(inspection_id, auth[0])


# 재점검 수동 어노테이션(수정/신규/삭제 바운딩 박스) 결과 임시 저장
@router.put("/reinspection-targets/{inspection_id}/annotations")
def save_reinspection_annotations(
    inspection_id: int,
    payload: ReinspectionAnnotationRequest,
    auth=Depends(current_auth),
):
    return inspection_service.save_reinspection_annotations(
        inspection_id, payload, auth[0]
    )
