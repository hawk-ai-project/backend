# models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from datetime import datetime
from database import Base

# 1. 기존 질문(Question) 테이블
class Question(Base):
    __tablename__ = "question"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    create_date = Column(DateTime, default=datetime.now)

# 2. CCTV 부유물 탐지 이력(DetectionLog) 테이블 (신규 프로젝트용)
class DetectionLog(Base):
    __tablename__ = "detection_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    camera_id = Column(String(50), nullable=False, index=True)  # CCTV 카메라 번호/ID
    object_type = Column(String(50), nullable=False)            # 탐지된 부유물 종류 (예: plastic, wood)
    confidence = Column(Float, nullable=False)                  # AI 신뢰도 (0.0~1.0)
    bbox_coordinates = Column(Text, nullable=True)              # 바운딩 박스 좌표 (JSON 텍스트)
    image_path = Column(String(255), nullable=True)             # 캡처 이미지 경로
    detected_at = Column(DateTime, default=datetime.now)        # 탐지 시간