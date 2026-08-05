# schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# [Question 관련 스키마]
class QuestionCreate(BaseModel):
    subject: str
    content: str

class QuestionUpdate(BaseModel):
    subject: str
    content: str

class Question(BaseModel):
    id: int
    subject: str
    content: str
    create_date: datetime  # str에서 datetime으로 변경

    class Config:
        from_attributes = True  # SQLAlchemy ORM 객체를 Pydantic으로 변환 허용 (Pydantic v2)


# [부유물 탐지 이력 스키마]
class DetectionLogCreate(BaseModel):
    camera_id: str
    object_type: str
    confidence: float
    bbox_coordinates: Optional[str] = None
    image_path: Optional[str] = None

class DetectionLog(DetectionLogCreate):
    id: int
    detected_at: datetime

    class Config:
        from_attributes = True