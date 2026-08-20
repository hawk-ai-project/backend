# backend/repository/waste_type_repository.py

from typing import Any
from common.db import fetch_query

def get_all_waste_types() -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT id, code, name_ko, name_en 
        FROM waste_types 
        ORDER BY id"""
    )
    
    # 결과가 리스트 형태면 반환, 아니면 빈 리스트 반환
    return rows if isinstance(rows, list) else []