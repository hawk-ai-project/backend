"""폐기물 유형 도메인의 직접 SQL 저장소."""
from typing import Any, Dict, List, Optional
from common.db import execute_query, fetch_query
from domain.waste import WasteCreate, WasteUpdate

def find_all() -> List[Dict[str, Any]]:
    rows = fetch_query(
        """SELECT id, code, name_ko, name_en, description, is_active, sort_order, created_at
           FROM waste_types           
           ORDER BY 
                CASE WHEN sort_order IS NULL THEN 1 ELSE 0 END, 
            sort_order ASC, 
            code ASC"""
    )
    return rows if isinstance(rows, list) else []

def find_by_id(waste_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_query(
        """SELECT id, code, name_ko, name_en, description, is_active, sort_order, created_at
           FROM waste_types
           WHERE id = %s""",
        (waste_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None

def create(waste: WasteCreate) -> int:
    return execute_query(
        """INSERT INTO waste_types (
            code, name_ko, name_en, description, is_active, sort_order
        ) VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            waste.code,
            waste.name_ko,
            waste.name_en,
            waste.description,
            waste.is_active,
            waste.sort_order,
        ),
    )

def update(waste_id: int, waste: WasteUpdate) -> bool:
    affected_rows = execute_query(
        """UPDATE waste_types
           SET code = %s,
               name_ko = %s,
               name_en = %s,
               description = %s,
               is_active = %s,
               sort_order = %s
           WHERE id = %s""",
        (
            waste.code,
            waste.name_ko,
            waste.name_en,
            waste.description,
            waste.is_active,
            waste.sort_order,
            waste_id,
        ),
    )
    return affected_rows > 0

def delete(waste_id: int) -> bool:
    """폐기물 유형을 완전히 삭제한다 (DELETE 쿼리 수행)."""
    affected_rows = execute_query(
        """DELETE FROM waste_types WHERE id = %s""",
        (waste_id,),
    )
    return affected_rows > 0