# backend/domain/inspection.py

from datetime import datetime

from pydantic import BaseModel, Field

# 프론트엔드에서 백엔드로
class InspectionRequest(BaseModel):
    image: str


class InspectionCreateRequest(BaseModel):
    image: str
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=150)
    notes: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class InspectionCreateResponse(BaseModel):
    inspectionId: int
    message: str
    detections: list["ObjectDetection"]

# 백엔드에서 프론트엔드로
class ObjectDetection(BaseModel):
    className: str
    confidence: float = Field(ge=0, le=1)
    bbox: list[float]


class DetectionReviewRequest(BaseModel):
    result: str = Field(pattern="^(TRUE_POSITIVE|FALSE_POSITIVE|FALSE_NEGATIVE|UNREVIEWED)$")
    actualClass: str | None = Field(default=None, max_length=100)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    errorReason: str | None = Field(default=None, max_length=500)
    reviewStatus: str = Field(default="REVIEWED", pattern="^(UNLABELED|LABELED|REVIEW_REQUIRED|REVIEWED|APPROVED|REJECTED)$")
    retrainingCandidate: bool = False


class MissedDetectionRequest(BaseModel):
    inspectionId: int = Field(gt=0)
    actualClass: str = Field(min_length=1, max_length=100)
    bbox: list[float] = Field(min_length=4, max_length=4)
    errorReason: str | None = Field(default=None, max_length=500)
    retrainingCandidate: bool = True


class DataTagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    categoryCode: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)


class DataBulkActionRequest(BaseModel):
    inspectionIds: list[int] = Field(min_length=1, max_length=500)
    action: str = Field(pattern="^(ADD_TAG|REMOVE_TAG|RETRAIN|APPROVE|REJECT|HARD_EXAMPLE)$")
    tagIds: list[int] = Field(default_factory=list, max_length=100)


class InspectionResponse(BaseModel):
    message: str = "이미지 분석이 완료되었습니다."
    detections: list[ObjectDetection]
    annotatedImage: str | None = None
    inferenceMs: int | None = None


class InspectionDetection(BaseModel):
    className: str
    count: int


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


class InspectionAssignee(BaseModel):
    id: int
    name: str
    role: str


class InspectionAssignmentRequest(BaseModel):
    assigneeId: int


class InspectionAssignmentResponse(BaseModel):
    inspectionId: int
    assignee: InspectionAssignee


class InspectionSaveRequest(BaseModel):
    title: str
    location_name: str
    coordinates: str
    notes: str | None = None
    address: str | None = None
    status: str
    image: str
    ai_detections: list[ObjectDetection]
