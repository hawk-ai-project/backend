"""메뉴 비즈니스 로직 서비스."""
from fastapi import HTTPException
from domain.menu import MenuCreate, MenuUpdate
from repository import menu_repository

def get_active_menus() -> list[dict]:
    return menu_repository.find_all_active()

def get_all_menus() -> list[dict]:
    return menu_repository.find_all()

def get_menu(menu_id: int) -> dict:
    menu = menu_repository.find_by_id(menu_id)
    if menu is None:
        raise HTTPException(status_code=404, detail="해당 메뉴를 찾을 수 없습니다.")
    return menu

def get_menu_tree() -> list[dict]:
    """DB의 Flat 메뉴 리스트를 Hierarchy Tree 구조로 변환한다."""
    raw_menus = menu_repository.find_all_active()
    
    menu_map = {}
    tree = []

    for item in raw_menus:
        item_id = item["id"]
        menu_node = {
            **item,
            "label": item["name"],
            "href": item["path"],
            "children": []
        }
        menu_map[item_id] = menu_node

    for item in raw_menus:
        item_id = item["id"]
        parent_id = item["parent_id"]

        if parent_id and parent_id in menu_map:
            menu_map[parent_id]["children"].append(menu_map[item_id])
        elif not parent_id:
            tree.append(menu_map[item_id])

    return tree

def create_menu(payload: MenuCreate) -> dict:
    new_id = menu_repository.create(payload)
    return get_menu(new_id)

def update_menu(menu_id: int, payload: MenuUpdate) -> dict:
    """메뉴 수정 비즈니스 로직"""
    get_menu(menu_id)  # 존재하지 않는 메뉴일 경우 404 HTTPException 발생
    menu_repository.update(menu_id, payload)
    return get_menu(menu_id)