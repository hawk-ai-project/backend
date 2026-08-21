"""폐기물 유형 도메인 모델."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class WasteBase(BaseModel):
    code: str
    name_ko: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    sort_order: Optional[int] = None

class WasteCreate(WasteBase):
    pass

class WasteUpdate(WasteBase):
    pass

class WasteResponse(WasteBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True