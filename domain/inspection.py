# backend/domain/inspection.py

from datetime import datetime

from pydantic import BaseModel, Field

# 프론트엔드에서 백엔드로
class InspectionRequest(BaseModel):
    image: str

# 백엔드에서 프론트엔드로
class ObjectDetection(BaseModel):
    className: str
    confidence: float = Field(ge=0, le=1)
    bbox: list[float]


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
