"""메뉴 도메인 모델."""

from typing import Literal

from pydantic import BaseModel


class MenuCreate(BaseModel):
    name: str
    path: str
    icon: str | None = None
    is_use: bool = True
    sort_order: int = 0
    parent_id: int | None = None
    menu_type: Literal["GROUP", "PAGE", "ACTION"] = "PAGE"
    description: str | None = None


class Menu(BaseModel):
    id: int
    parent_id: int | None
    name: str
    path: str
    icon: str | None
    menu_type: str
    description: str | None
    is_use: bool
    sort_order: int
