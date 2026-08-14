from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FavoriteCreate(BaseModel):
    menu_id: Optional[int] = None
    title: str
    path: str
    icon: Optional[str] = "star"

class FavoriteResponse(BaseModel):
    id: int
    user_id: int
    menu_id: Optional[int] = None
    title: str
    path: str
    icon: Optional[str] = None
    visit_count: int
    last_visited_at: datetime

    class Config:
        from_attributes = True