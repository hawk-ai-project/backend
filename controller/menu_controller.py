from fastapi import APIRouter

from domain.menu import Menu, MenuCreate
from service import menu_service


router = APIRouter(prefix="/api/menu", tags=["menu"])


@router.get("/list", response_model=list[Menu])
def get_menu_list():
    return menu_service.get_active_menus()


@router.get("/{menu_id}", response_model=Menu)
def get_menu_detail(menu_id: int):
    return menu_service.get_menu(menu_id)


@router.post("", response_model=Menu)
def create_menu(payload: MenuCreate):
    return menu_service.create_menu(payload)
