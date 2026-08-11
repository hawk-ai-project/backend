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


def find_or_create_location(name: str, user_id: int) -> int:
    existing = fetch_query(
        "SELECT id FROM locations WHERE name = %s AND is_active = TRUE ORDER BY id LIMIT 1",
        (name,), one=True,
    )
    if isinstance(existing, dict):
        return int(existing["id"])
    return execute_query(
        "INSERT INTO locations (name, created_by) VALUES (%s, %s)",
        (name, user_id),
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
