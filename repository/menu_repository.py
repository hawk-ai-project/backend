"""메뉴 도메인의 직접 SQL 저장소."""
from typing import Any, Dict, List, Optional
from common.db import execute_query, fetch_query
from domain.menu import MenuCreate, MenuUpdate

def find_all_active() -> List[Dict[str, Any]]:
    """사용 중인 메뉴 목록을 정렬 순서대로 조회한다."""
    rows = fetch_query(
        """SELECT id, parent_id, name, path, icon, menu_type,
                  description, is_use, sort_order, is_admin_only, created_at, updated_at
           FROM menu
           WHERE is_use = TRUE
           ORDER BY sort_order ASC, id ASC"""
    )
    return rows if isinstance(rows, list) else []

def find_all() -> List[Dict[str, Any]]:
    """전체 메뉴 목록을 조회한다 (관리자용)."""
    rows = fetch_query(
        """SELECT id, parent_id, name, path, icon, menu_type,
                  description, is_use, sort_order, is_admin_only, created_at, updated_at
           FROM menu
           ORDER BY parent_id ASC, sort_order ASC, id ASC"""
    )
    return rows if isinstance(rows, list) else []

def find_by_id(menu_id: int) -> Optional[Dict[str, Any]]:
    """식별자에 해당하는 메뉴 한 건을 조회한다."""
    row = fetch_query(
        """SELECT id, parent_id, name, path, icon, menu_type,
                  description, is_use, sort_order, is_admin_only, created_at, updated_at
           FROM menu
           WHERE id = %s""",
        (menu_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None

def create(menu: MenuCreate) -> int:
    """새 메뉴를 등록하고 생성된 식별자를 반환한다."""
    return execute_query(
        """INSERT INTO menu (
            parent_id, name, path, icon, menu_type,
            description, is_use, sort_order, is_admin_only
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            menu.parent_id,
            menu.name,
            menu.path,
            menu.icon,
            menu.menu_type.value if hasattr(menu.menu_type, 'value') else menu.menu_type,
            menu.description,
            menu.is_use,
            menu.sort_order,
            menu.is_admin_only, # ★ 추가
        ),
    )

def update(menu_id: int, menu: MenuUpdate) -> bool:
    """메뉴 정보를 수정한다."""
    affected_rows = execute_query(
        """UPDATE menu
           SET parent_id = %s,
               name = %s,
               path = %s,
               icon = %s,
               menu_type = %s,
               description = %s,
               is_use = %s,
               sort_order = %s,
               is_admin_only = %s,
               updated_at = NOW()
           WHERE id = %s""",
        (
            menu.parent_id,
            menu.name,
            menu.path,
            menu.icon,
            menu.menu_type.value if hasattr(menu.menu_type, 'value') else menu.menu_type,
            menu.description,
            menu.is_use,
            menu.sort_order,
            menu.is_admin_only, # ★ 추가
            menu_id,
        ),
    )
    return affected_rows > 0