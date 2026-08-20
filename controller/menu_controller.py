from fastapi import APIRouter
from domain.menu import MenuCreate, MenuUpdate
from service import menu_service

router = APIRouter(prefix="/api/menus", tags=["menu"])

@router.get("/tree")
def get_menu_tree():
    """상단 내비게이션용 트리형 메뉴 조회 API"""
    return menu_service.get_menu_tree()

@router.get("")
def get_all_menus():
    """전체 메뉴 목록 조회 API (관리자용)"""
    return menu_service.get_all_menus()

@router.get("/{menu_id}")
def get_menu_detail(menu_id: int):
    """특정 메뉴 상세 조회 API"""
    return menu_service.get_menu(menu_id)

@router.post("")
def create_menu(payload: MenuCreate):
    """신규 메뉴 생성 API"""
    return menu_service.create_menu(payload)

@router.patch("/{menu_id}")
def update_menu(menu_id: int, payload: MenuUpdate):
    """메뉴 수정 API"""
    return menu_service.update_menu(menu_id, payload)