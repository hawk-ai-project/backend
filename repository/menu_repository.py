"""메뉴 도메인의 직접 SQL 저장소."""

from typing import Any

from common.db import execute_query, fetch_query


def find_active() -> list[dict[str, Any]]:
    """사용 중인 메뉴를 표시 순서대로 조회한다."""
    rows = fetch_query(
        """SELECT id, parent_id, name, path, icon, menu_type,
                  description, is_use, sort_order
        FROM menu
        WHERE is_use = TRUE
        ORDER BY sort_order ASC, id ASC"""
    )
    return rows if isinstance(rows, list) else []


def find_by_id(menu_id: int) -> dict[str, Any] | None:
    """식별자에 해당하는 메뉴 한 건을 조회한다."""
    row = fetch_query(
        """SELECT id, parent_id, name, path, icon, menu_type,
                  description, is_use, sort_order
        FROM menu
        WHERE id = %s""",
        (menu_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def create(data: dict[str, Any]) -> int:
    """새 메뉴를 등록하고 생성된 식별자를 반환한다."""
    return execute_query(
        """INSERT INTO menu (
            parent_id, name, path, icon, menu_type,
            description, is_use, sort_order
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            data["parent_id"], data["name"], data["path"], data["icon"],
            data["menu_type"], data["description"], data["is_use"],
            data["sort_order"],
        ),
    )
