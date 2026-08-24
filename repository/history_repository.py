from typing import Dict, Any, List
from common.db import execute_query, fetch_query


def find_active_assignees() -> List[Dict[str, Any]]:
    """
    담당자로 지정 가능한 활성 사용자 목록(일반 사용자 제외)을 조회합니다.
    """
    sql = """
        SELECT /* find_active_assignees_sql */
            u.id,
            u.name,
            r.code AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.deleted_at IS NULL
          AND u.status = 'ACTIVE'
          AND r.code <> 'USER'
        ORDER BY u.name, u.id
    """
    rows = fetch_query(sql) or []
    return rows


def find_accessible_inspection(inspection_id: int, user_id: int, is_admin: bool) -> Dict[str, Any] | None:
    """
    사용자 권한(관리자 여부)에 따라 접근 가능한 점검 이력인지 확인합니다.
    """
    permission = "" if is_admin else "AND i.inspector_id = %s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)

    sql = f"""
        SELECT /* find_accessible_inspection_sql */
            i.id
        FROM inspections i
        WHERE i.id = %s
          AND i.deleted_at IS NULL
          {permission}
    """
    row = fetch_query(sql, params, one=True)
    return row if isinstance(row, dict) else None


def soft_delete_inspection(inspection_id: int) -> bool:
    """
    점검 이력을 소프트 삭제(deleted_at 기록) 처리합니다.
    """
    sql = """
        UPDATE /* soft_delete_inspection_sql */
            inspections
        SET deleted_at = UTC_TIMESTAMP(6),
            updated_at = UTC_TIMESTAMP(6)
        WHERE id = %s
          AND deleted_at IS NULL
    """
    affected = execute_query(sql, (inspection_id,))
    return affected > 0


def find_active_user(user_id: int) -> Dict[str, Any] | None:
    """
    담당자로 배정할 사용자가 유효한 활성 계정인지 검증합니다.
    """
    sql = """
        SELECT /* find_active_user_sql */
            u.id,
            u.name,
            r.code AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
          AND u.deleted_at IS NULL
          AND u.status = 'ACTIVE'
          AND r.code <> 'USER'
    """
    row = fetch_query(sql, (user_id,), one=True)
    return row if isinstance(row, dict) else None


def assign_inspection(inspection_id: int, assignee_id: int, created_by: int) -> None:
    """
    점검 이력에 담당자를 신규 지정하거나 기존 조치(inspection_actions) 내역을 업데이트합니다.
    """
    check_sql = """
        SELECT /* assign_inspection_check_sql */
            id
        FROM inspection_actions
        WHERE inspection_id = %s
          AND action_type IN ('COLLECTION_REQUEST', 'COLLECTION')
          AND status <> 'CANCELLED'
        ORDER BY id DESC
        LIMIT 1
    """
    existing = fetch_query(check_sql, (inspection_id,), one=True)

    if isinstance(existing, dict):
        update_sql = """
            UPDATE /* assign_inspection_update_sql */
                inspection_actions
            SET assignee_id = %s,
                updated_at = UTC_TIMESTAMP(6)
            WHERE id = %s
        """
        execute_query(update_sql, (assignee_id, existing["id"]))
    else:
        insert_sql = """
            INSERT INTO inspection_actions /* assign_inspection.insert_sql */
            (inspection_id, assignee_id, created_by, action_type, status, description)
            VALUES (%s, %s, %s, 'COLLECTION_REQUEST', 'OPEN', '현장 수거 담당자 배정')
        """
        execute_query(insert_sql, (inspection_id, assignee_id, created_by))

    execute_query(
        """UPDATE inspections
           SET status = 'ACTION_REQUIRED', updated_at = UTC_TIMESTAMP(6)
           WHERE id = %s AND deleted_at IS NULL
             AND status <> 'RESOLVED'""",
        (inspection_id,),
    )

def update_notes(inspection_id: int, notes: str) -> None:
    """
    점검 이력의 점검 의견 및 후속 조치(notes)를 업데이트합니다.
    """
    sql = """
        UPDATE /* update_notes_sql */
            inspections
        SET notes = %s,
            updated_at = UTC_TIMESTAMP(6)
        WHERE id = %s
          AND deleted_at IS NULL
    """
    execute_query(sql, (notes, inspection_id))


def find_inspection_detail(inspection_id: int, user_id: int, is_admin: bool) -> Dict[str, Any] | None:
    permission = "" if is_admin else "AND i.inspector_id = %s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)

    sql = f"""
        SELECT /* find_inspection_detail_sql */
            i.id,
            COALESCE(i.title, '') AS title,
            l.name AS location,
            CASE 
                WHEN l.latitude IS NOT NULL AND l.longitude IS NOT NULL 
                THEN CONCAT('위도 : ', l.latitude, ', 경도 : ', l.longitude)
                ELSE NULL 
            END AS coordinates,
            i.captured_at,
            i.status,
            i.priority,
            i.notes,
            i.ai_opinion,
            NULL AS waste_summary,
            NULL AS detections,
            NULL AS image_id,
            u.name AS inspector_name
        FROM inspections i
        LEFT JOIN users u ON u.id = i.inspector_id
        LEFT JOIN locations l ON l.id = i.location_id
        WHERE i.id = %s
          AND i.deleted_at IS NULL
          {permission}
    """
    row = fetch_query(sql, params, one=True)
    return row if isinstance(row, dict) else None


def insert_inspection_image(
    inspection_id: int,
    kind: str,
    storage_key: str,
    original_name: str,
    mime_type: str,
    byte_size: int,
    width: int | None = None,
    height: int | None = None,
    sha256: str | None = None,
) -> int:
    """
    수거 완료 증빙 사진 등 점검 이미지 메타데이터를 신규 저장합니다.
    """
    sql = """
        INSERT INTO inspection_images /* insert_inspection_image_sql */ (
            inspection_id,
            kind,
            storage_key,
            original_name,
            mime_type,
            byte_size,
            width,
            height,
            sha256
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    return execute_query(
        sql,
        (
            inspection_id,
            kind,
            storage_key,
            original_name,
            mime_type,
            byte_size,
            width,
            height,
            sha256,
        ),
    )