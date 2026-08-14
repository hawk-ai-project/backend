from typing import List, Dict, Any
# 💡 database 대신 common.db를 import 합니다.
from common.db import fetch_query, execute_query


def find_top5_by_user_id(user_id: int) -> List[Dict[str, Any]]:
    """사용자별 상위 5개 즐겨찾기 목록을 조회합니다. (메인 페이지 '/' 제외)"""
    sql = """
        SELECT /* find_top5_by_user_id.sql */
            id, user_id, menu_id, title, path, icon, visit_count, last_visited_at
        FROM user_favorites
        WHERE user_id = %s AND path != '/'
        ORDER BY visit_count DESC, last_visited_at DESC
        LIMIT 5
    """
    return fetch_query(sql, (user_id,)) or []


def increment_visit_count(favorite_id: int, user_id: int) -> bool:
    """즐겨찾기 방문 횟수 및 최근 방문 일시를 업데이트합니다."""
    sql = """
        UPDATE /* increment_visit_count.sql */
            user_favorites
        SET visit_count = visit_count + 1,
            last_visited_at = CURRENT_TIMESTAMP(6)
        WHERE id = %s AND user_id = %s
    """
    affected_rows = execute_query(sql, (favorite_id, user_id))
    return (affected_rows or 0) > 0


def upsert_favorite(user_id: int, menu_id: int | None, title: str, path: str, icon: str | None) -> bool:
    """즐겨찾기를 추가하거나, 이미 존재할 경우 방문 횟수 및 일시를 업데이트합니다."""
    sql = """
        INSERT INTO /* upsert_favorite.sql */ user_favorites (
            user_id, menu_id, title, path, icon, visit_count
        )
        VALUES (%s, %s, %s, %s, %s, 1)
        ON DUPLICATE KEY UPDATE
            visit_count = visit_count + 1,
            last_visited_at = CURRENT_TIMESTAMP(6)
    """
    affected_rows = execute_query(sql, (user_id, menu_id, title, path, icon))
    return (affected_rows or 0) > 0


def delete_by_id(favorite_id: int, user_id: int) -> bool:
    """지정된 즐겨찾기 항목을 삭제합니다."""
    sql = """
        DELETE /* delete_by_id.sql */
        FROM user_favorites
        WHERE id = %s AND user_id = %s
    """
    affected_rows = execute_query(sql, (favorite_id, user_id))
    return (affected_rows or 0) > 0