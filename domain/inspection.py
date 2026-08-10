# backend/domain/inspection.py

from pydantic import BaseModel

# 프론트엔드에서 백엔드로
class InspectionRequest(BaseModel):
    image: str

# 백엔드에서 프론트엔드로
class InspectionResponse(BaseModel):
    message: str
    result: str