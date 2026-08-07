from fastapi import HTTPException

from domain.menu import MenuCreate
from repository import menu_repository


def get_active_menus() -> list[dict]:
    return menu_repository.find_active()


def get_menu(menu_id: int) -> dict:
    menu = menu_repository.find_by_id(menu_id)
    if menu is None:
        raise HTTPException(status_code=404, detail="해당 메뉴를 찾을 수 없습니다.")
    return menu


def create_menu(payload: MenuCreate) -> dict:
    return get_menu(menu_repository.create(payload.model_dump()))
