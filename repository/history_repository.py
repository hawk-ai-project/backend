from typing import Any, Dict, List, Optional
from common.db import fetch_query, execute_query


def find_inspection_history(
    limit: int = 100, user_id: Optional[int] = None, is_admin: bool = False
) -> List[Dict[str, Any]]:
    """점검 이력 목록 조회"""
    query = """
        /* find_inspection_history.sql */
        SELECT 
            i.id,
            CONCAT('INSPECTION-', i.id) AS inspection_no,
            i.title,
            COALESCE(loc.name, loc.address, '') AS location,
            CASE 
                WHEN loc.latitude IS NOT NULL AND loc.longitude IS NOT NULL 
                THEN CONCAT(loc.latitude, ',', loc.longitude)
                ELSE ''
            END AS coordinates,
            COALESCE(
                DATE_FORMAT(i.captured_at, '%%Y-%%m-%%d %%H:%%i:%%s'), 
                DATE_FORMAT(i.created_at, '%%Y-%%m-%%d %%H:%%i:%%s'), 
                '-'
            ) AS captured_at,
            i.status,
            i.priority,
            i.notes,
            i.ai_opinion,
            COALESCE(u.name, '') AS inspector_name,
            COALESCE(dt_summary.total_count, 0) AS detection_count,
            COALESCE(dt_summary.detections_json, '[]') AS detections,
            img.id AS image_id,
            i.inspector_id AS assignee_id,
            u.name AS assignee_name
        FROM inspections i
        LEFT JOIN locations loc ON i.location_id = loc.id
        LEFT JOIN users u ON i.inspector_id = u.id
        LEFT JOIN (
            SELECT inspection_id, MIN(id) AS id
            FROM inspection_images
            WHERE kind = 'ORIGINAL'
            GROUP BY inspection_id
        ) img ON i.id = img.inspection_id
        LEFT JOIN (
            SELECT 
                dr.inspection_id,
                COUNT(d.id) AS total_count,
                JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'waste_type_id', d.waste_type_id,
                        'name_ko', COALESCE(wt.name_ko, '알 수 없음'),
                        'count', 1
                    )
                ) AS detections_json
            FROM detection_runs dr
            JOIN detections d ON dr.id = d.detection_run_id
            LEFT JOIN waste_types wt ON d.waste_type_id = wt.id
            GROUP BY dr.inspection_id
        ) dt_summary ON i.id = dt_summary.inspection_id
        WHERE i.deleted_at IS NULL
    """
    params = []
    if not is_admin and user_id is not None:
        query += " AND i.inspector_id = %s"
        params.append(user_id)

    query += " ORDER BY i.id DESC LIMIT %s"
    params.append(limit)

    return fetch_query(query, tuple(params))


def find_inspection_detail(
    inspection_id: int, user_id: Optional[int] = None, is_admin: bool = False
) -> Optional[Dict[str, Any]]:
    """점검 이력 단건 상세 조회"""
    query = """
        /* find_inspection_detail.sql */
        SELECT 
            i.id,
            CONCAT('INSPECTION-', i.id) AS inspection_no,
            i.title,
            COALESCE(loc.name, loc.address, '') AS location,
            CASE 
                WHEN loc.latitude IS NOT NULL AND loc.longitude IS NOT NULL 
                THEN CONCAT(loc.latitude, ',', loc.longitude)
                ELSE ''
            END AS coordinates,
            COALESCE(
                DATE_FORMAT(i.captured_at, '%%Y-%%m-%%d %%H:%%i:%%s'), 
                DATE_FORMAT(i.created_at, '%%Y-%%m-%%d %%H:%%i:%%s'), 
                '-'
            ) AS captured_at,
            i.status,
            i.priority,
            i.notes,
            i.ai_opinion,
            COALESCE(u.name, '') AS inspector_name,
            COALESCE(dt_summary.total_count, 0) AS detection_count,
            COALESCE(dt_summary.detections_json, '[]') AS detections,
            img.id AS image_id,
            i.inspector_id AS assignee_id,
            u.name AS assignee_name
        FROM inspections i
        LEFT JOIN locations loc ON i.location_id = loc.id
        LEFT JOIN users u ON i.inspector_id = u.id
        LEFT JOIN (
            SELECT inspection_id, MIN(id) AS id
            FROM inspection_images
            WHERE kind = 'ORIGINAL'
            GROUP BY inspection_id
        ) img ON i.id = img.inspection_id
        LEFT JOIN (
            SELECT 
                dr.inspection_id,
                COUNT(d.id) AS total_count,
                JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'waste_type_id', d.waste_type_id,
                        'name_ko', COALESCE(wt.name_ko, '알 수 없음'),
                        'count', 1
                    )
                ) AS detections_json
            FROM detection_runs dr
            JOIN detections d ON dr.id = d.detection_run_id
            LEFT JOIN waste_types wt ON d.waste_type_id = wt.id
            GROUP BY dr.inspection_id
        ) dt_summary ON i.id = dt_summary.inspection_id
        WHERE i.id = %s AND i.deleted_at IS NULL
    """
    params = [inspection_id]
    if not is_admin and user_id is not None:
        query += " AND i.inspector_id = %s"
        params.append(user_id)

    rows = fetch_query(query, tuple(params))
    return rows[0] if rows else None


def find_accessible_inspection(
    inspection_id: int, user_id: int, is_admin: bool = False
) -> Optional[Dict[str, Any]]:
    query = """
        /* find_accessible_inspection.sql */
        SELECT id FROM inspections WHERE id = %s AND deleted_at IS NULL
    """
    params = [inspection_id]
    if not is_admin:
        query += " AND inspector_id = %s"
        params.append(user_id)

    rows = fetch_query(query, tuple(params))
    return rows[0] if rows else None


def soft_delete_inspection(inspection_id: int) -> bool:
    query = """
        /* soft_delete_inspection.sql */
        UPDATE inspections SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL
    """
    rowcount = execute_query(query, (inspection_id,))
    return rowcount > 0


def find_active_assignees() -> List[Dict[str, Any]]:
    query = """
        /* find_active_assignees.sql */
        SELECT u.id, u.name, u.email, r.code AS role 
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.status = 'ACTIVE' AND u.deleted_at IS NULL AND r.code IN ('ADMIN', 'MANAGER', 'INSPECTOR')
        ORDER BY u.name ASC
    """
    return fetch_query(query)


def find_active_user(user_id: int) -> Optional[Dict[str, Any]]:
    query = """
        /* find_active_user.sql */
        SELECT u.id, u.name, r.code AS role 
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.id = %s AND u.status = 'ACTIVE' AND u.deleted_at IS NULL
    """
    rows = fetch_query(query, (user_id,))
    return rows[0] if rows else None


def assign_inspection(inspection_id: int, assignee_id: int, updated_by: int) -> None:
    query = """
        /* assign_inspection.sql */
        UPDATE inspections 
        SET inspector_id = %s, status = 'ACTION_REQUIRED', updated_at = NOW() 
        WHERE id = %s
    """
    execute_query(query, (assignee_id, inspection_id))


def update_notes(inspection_id: int, notes: str) -> None:
    query = """
        /* update_notes.sql */
        UPDATE inspections SET notes = %s, updated_at = NOW() WHERE id = %s
    """
    execute_query(query, (notes, inspection_id))


def insert_inspection_image(
    inspection_id: int,
    kind: str,
    storage_key: str,
    original_name: str,
    mime_type: str,
    byte_size: int,
    width: Optional[int],
    height: Optional[int],
    sha256: str,
) -> int:
    query = """
        /* insert_inspection_image.sql */
        INSERT INTO inspection_images (
            inspection_id, kind, storage_key, original_name, 
            mime_type, byte_size, width, height, sha256, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    params = (
        inspection_id,
        kind,
        storage_key,
        original_name,
        mime_type,
        byte_size,
        width,
        height,
        sha256,
    )
    return execute_query(query, params, return_last_id=True)