"""메뉴 도메인 모델."""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class MenuType(str, Enum):
    GROUP = "GROUP"
    PAGE = "PAGE"
    ACTION = "ACTION"

class MenuBase(BaseModel):
    parent_id: Optional[int] = None
    name: str
    path: str
    icon: Optional[str] = None
    menu_type: MenuType = MenuType.PAGE
    description: Optional[str] = None
    is_use: bool = True
    sort_order: int = 0
    is_admin_only: bool = False

class MenuCreate(MenuBase):
    pass

class MenuResponse(MenuBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MenuTreeResponse(MenuResponse):
    label: str
    href: str
    children: List["MenuTreeResponse"] = []

class MenuUpdate(MenuBase):
    pass