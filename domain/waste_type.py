# backend/domain/waste_type.py

from pydantic import BaseModel, Field

class WasteDetectionRequest(BaseModel):
    waste_type_id: int = Field(gt=0, description="폐기물 종류 ID")
    count: int = Field(ge=1, description="수동으로 입력한 폐기물 수량")

class WasteTypeResponse(BaseModel):
    id: int
    code: str = Field(min_length=1, max_length=50)
    name_ko: str = Field(min_length=1, max_length=100)
    name_en: str = Field(min_length=1, max_length=100)

    class Config:
        from_attributes = True