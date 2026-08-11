# backend/domain/inspection.py

from datetime import datetime

from pydantic import BaseModel

# 프론트엔드에서 백엔드로
class InspectionRequest(BaseModel):
    image: str

# 백엔드에서 프론트엔드로
class InspectionResponse(BaseModel):
    message: str
    result: str


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
