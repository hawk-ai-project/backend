# backend/domain/history.py
from datetime import datetime
from pydantic import BaseModel

class InspectionDetection(BaseModel):
    className: str
    count: int

class InspectionHistoryItem(BaseModel):
    id: int
    title: str | None = ""
    location: str | None = ""
    coordinates: str | None = None
    capturedAt: str | datetime | None = None
    status: str | None = None
    priority: str | None = None
    notes: str | None = None
    aiOpinion: str | None = None
    inspectorName: str | None = None
    wasteSummary: str | None = None
    detections: list = []
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