from typing import Any

from common.db import execute_query, fetch_query


def find_active_assignees() -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT u.id, u.name, r.code AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.deleted_at IS NULL AND u.status = 'ACTIVE'
          AND r.code <> 'USER'
        ORDER BY u.name, u.id"""
    )
    return rows if isinstance(rows, list) else []


def find_or_create_location(
    name: str, user_id: int, latitude: float | None = None, longitude: float | None = None,
) -> int:
    existing = fetch_query(
        "SELECT id FROM locations WHERE name = %s AND is_active = TRUE ORDER BY id LIMIT 1",
        (name,), one=True,
    )
    if isinstance(existing, dict):
        if latitude is not None and longitude is not None:
            execute_query(
                "UPDATE locations SET latitude = %s, longitude = %s WHERE id = %s",
                (latitude, longitude, existing["id"]),
            )
        return int(existing["id"])
    return execute_query(
        "INSERT INTO locations (name, latitude, longitude, created_by) VALUES (%s, %s, %s, %s)",
        (name, latitude, longitude, user_id),
    )


def create_inspection(location_id: int, user_id: int, title: str, notes: str | None) -> int:
    return execute_query(
        """INSERT INTO inspections
        (location_id, inspector_id, title, notes, status, priority, captured_at)
        VALUES (%s, %s, %s, %s, 'REVIEW_REQUIRED', 'MEDIUM', UTC_TIMESTAMP(6))""",
        (location_id, user_id, title, notes),
    )


def create_inspection_image(inspection_id: int, kind: str, stored: dict[str, Any]) -> int:
    return execute_query(
        """INSERT INTO inspection_images
        (inspection_id, kind, storage_key, original_name, mime_type, byte_size, sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (inspection_id, kind, stored["storageKey"], stored["originalName"],
         stored["mimeType"], stored["byteSize"], stored["sha256"]),
    )


def update_location_coordinates(location_id: int, latitude: float, longitude: float) -> None:
    execute_query(
        "UPDATE locations SET latitude = %s, longitude = %s WHERE id = %s",
        (latitude, longitude, location_id),
    )


def find_accessible_inspection(inspection_id: int, user_id: int, is_admin: bool) -> dict[str, Any] | None:
    permission = "" if is_admin else "AND i.inspector_id = %s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)
    row = fetch_query(
        f"""SELECT i.id
        FROM inspections i
        WHERE i.id = %s AND i.deleted_at IS NULL {permission}""",
        params,
        one=True,
    )
    return row if isinstance(row, dict) else None


def find_active_user(user_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT u.id, u.name, r.code AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s AND u.deleted_at IS NULL
          AND u.status = 'ACTIVE' AND r.code <> 'USER'""",
        (user_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def assign_inspection(inspection_id: int, assignee_id: int, created_by: int) -> None:
    existing = fetch_query(
        """SELECT id FROM inspection_actions
        WHERE inspection_id = %s
          AND action_type IN ('COLLECTION_REQUEST', 'COLLECTION')
          AND status <> 'CANCELLED'
        ORDER BY id DESC LIMIT 1""",
        (inspection_id,),
        one=True,
    )
    if isinstance(existing, dict):
        execute_query(
            """UPDATE inspection_actions
            SET assignee_id = %s, updated_at = UTC_TIMESTAMP(6)
            WHERE id = %s""",
            (assignee_id, existing["id"]),
        )
        return

    execute_query(
        """INSERT INTO inspection_actions
        (inspection_id, assignee_id, created_by, action_type, status, description)
        VALUES (%s, %s, %s, 'COLLECTION_REQUEST', 'OPEN', '현장 수거 담당자 배정')""",
        (inspection_id, assignee_id, created_by),
    )


def insert_inspection_record(payload, user_id: int, ai_opinion: str):
    # 프론트엔드에서 보낸 "35.1587,129.1604" 형태의 문자열을 반으로 쪼개서 위도/경도 숫자로 만들기
    lat, lon = 0.0, 0.0
    if payload.coordinates and "," in payload.coordinates:
        coords = payload.coordinates.split(",")
        lat = float(coords[0].strip())
        lon = float(coords[1].strip())

    # locations에 새 장소 추가
    execute_query(
        """INSERT INTO locations 
        (name, latitude, longitude, is_active, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, 1, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())""",
        (payload.location_name, lat, lon, user_id)
    )
    
    # inspections에 방금 만든 장소 번호(id)를 달아서 기록
    execute_query(
        """INSERT INTO inspections 
        (location_id, inspector_id, title, notes, ai_opinion, status, priority, captured_at, created_at, updated_at)
        VALUES (
            (SELECT id FROM locations WHERE name = %s ORDER BY created_at DESC LIMIT 1), 
            %s, %s, %s, %s, %s, 'MEDIUM', UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP()
        )""",
        (payload.location_name, user_id, payload.title, payload.notes, ai_opinion, payload.status)
    )