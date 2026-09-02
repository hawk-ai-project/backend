# backend/domain/inspection.py

from datetime import datetime

from pydantic import BaseModel, Field
from domain.waste_type import WasteDetectionRequest

# ==============================================================================
# 1. 점검 생성 및 분석 요청 DTO (Frontend -> Backend)
# ==============================================================================


# 단순 이미지 AI 분석 요청
class InspectionRequest(BaseModel):
    image: str


# 신규 현장 점검 등록 요청 (위치/좌표/메모 포함)
class InspectionCreateRequest(BaseModel):
    image: str
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=150)
    notes: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


# 현장 점검 등록 완료 응답
class InspectionCreateResponse(BaseModel):
    inspectionId: int
    message: str
    detections: list["ObjectDetection"]


# 현장 점검 및 수동 라벨링 복합 저장 요청
class InspectionSaveRequest(BaseModel):
    title: str
    location_name: str
    coordinates: str
    notes: str | None = None
    address: str | None = None
    status: str
    image: str
    ai_detections: list["ObjectDetection"]
    detections: list[WasteDetectionRequest] = Field(default_factory=list)


# ==============================================================================
# 2. 객체 탐지 및 AI 분석 응답 DTO (Backend -> Frontend)
# ==============================================================================


# 단일 탐지 객체 정보 (클래스명, 신뢰도, 정규화 바운딩 박스)
class ObjectDetection(BaseModel):
    className: str
    confidence: float = Field(ge=0, le=1)
    bbox: list[float]


# AI 이미지 추론 최종 응답 (탐지 목록, 시각화 이미지, 소요 시간)
class InspectionResponse(BaseModel):
    message: str = "이미지 분석이 완료되었습니다."
    detections: list[ObjectDetection]
    annotatedImage: str | None = None
    inferenceMs: int | None = None


# 점검 요약용 폐기물 종류별 탐지 집계 건수
class InspectionDetection(BaseModel):
    className: str
    count: int


# ==============================================================================
# 3. 재점검 및 수동 라벨링/검토 DTO
# ==============================================================================


# AI 탐지 객체 검토 및 수정 요청 (오탐/정탐 판정 및 라벨 변경)
class DetectionReviewRequest(BaseModel):
    result: str = Field(
        pattern="^(TRUE_POSITIVE|FALSE_POSITIVE|FALSE_NEGATIVE|UNREVIEWED)$"
    )
    actualClass: str | None = Field(default=None, max_length=100)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    errorReason: str | None = Field(default=None, max_length=500)
    reviewStatus: str = Field(
        default="REVIEWED",
        pattern="^(UNLABELED|LABELED|REVIEW_REQUIRED|REVIEWED|APPROVED|REJECTED)$",
    )
    retrainingCandidate: bool = False


# AI가 놓친 미탐지 객체(False Negative) 수동 추가 요청
class MissedDetectionRequest(BaseModel):
    inspectionId: int = Field(gt=0)
    actualClass: str = Field(min_length=1, max_length=100)
    bbox: list[float] = Field(min_length=4, max_length=4)
    errorReason: str | None = Field(default=None, max_length=500)
    retrainingCandidate: bool = True


# ==============================================================================
# 4. 데이터 태그 및 일괄 작업(Bulk Action) DTO
# ==============================================================================


# 데이터 분류 태그 생성 요청
class DataTagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    categoryCode: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)


# 복수 점검 건 일괄 처리 요청 (태그 지정, 재학습 등록, 승인/반려 등)
class DataBulkActionRequest(BaseModel):
    inspectionIds: list[int] = Field(min_length=1, max_length=500)
    action: str = Field(
        pattern="^(ADD_TAG|REMOVE_TAG|RETRAIN|APPROVE|REJECT|HARD_EXAMPLE)$"
    )
    tagIds: list[int] = Field(default_factory=list, max_length=100)


# ==============================================================================
# 5. 점검 이력 및 담당자 배정 DTO
# ==============================================================================


# 점검 이력 목록 및 상세 단건 조회 항목
class InspectionHistoryItem(BaseModel):
    id: int
    title: str
    location: str
    coordinates: str | None = None
    capturedAt: datetime
    status: str
    priority: str
    notes: str | None = None
    aiOpinion: str | None = None
    inspectorName: str
    wasteSummary: str
    detections: list[InspectionDetection]
    imageId: int | None = None
    assigneeId: int | None = None
    assigneeName: str | None = None


# 작업/수거 담당자 기본 정보
class InspectionAssignee(BaseModel):
    id: int
    name: str
    role: str


# 현장 수거 담당자 배정 요청
class InspectionAssignmentRequest(BaseModel):
    assigneeId: int


# 현장 수거 담당자 배정 결과 응답
class InspectionAssignmentResponse(BaseModel):
    inspectionId: int
    assignee: InspectionAssignee
