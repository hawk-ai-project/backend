"""Database access for MinIO file metadata."""

from typing import Any

from common.db import execute_query, fetch_query


def create(*, uploaded_by: int, bucket_name: str, object_key: str,
           original_name: str, mime_type: str, byte_size: int,
           etag: str | None) -> int:
    return execute_query(
        """INSERT INTO files
           (uploaded_by, bucket_name, object_key, original_name, mime_type, byte_size, etag)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (uploaded_by, bucket_name, object_key, original_name, mime_type, byte_size, etag),
    )


def find_owned_active(object_key: str, user_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT id, uploaded_by, bucket_name, object_key, original_name,
                  mime_type, byte_size, etag, created_at
           FROM files
           WHERE object_key = %s AND uploaded_by = %s AND deleted_at IS NULL""",
        (object_key, user_id), one=True,
    )
    return row if isinstance(row, dict) else None


def soft_delete(file_id: int, user_id: int) -> bool:
    affected = execute_query(
        """UPDATE files
           SET deleted_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
           WHERE id = %s AND uploaded_by = %s AND deleted_at IS NULL""",
        (file_id, user_id),
    )
    return affected > 0

