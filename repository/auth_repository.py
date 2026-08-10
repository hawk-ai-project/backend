"""Database access for users and authentication sessions."""

from datetime import datetime
from typing import Any

from common.db import execute_query, fetch_query


def find_user_by_email(email: str) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT u.id, u.name, u.email, u.password_hash, u.status,
                  u.profile_file_id AS profileFileId,
                  r.code AS role
           FROM users u
           JOIN roles r ON r.id = u.role_id
           WHERE u.email = %s AND u.deleted_at IS NULL""",
        (email,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def find_user_by_id(user_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT u.id, u.name, u.email, u.status,
                  u.profile_file_id AS profileFileId, r.code AS role
           FROM users u
           JOIN roles r ON r.id = u.role_id
           WHERE u.id = %s AND u.deleted_at IS NULL""",
        (user_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def find_user_credentials_by_id(user_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        "SELECT id, email, password_hash FROM users WHERE id = %s AND deleted_at IS NULL",
        (user_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def create_user(name: str, email: str, password_hash: str) -> int:
    return execute_query(
        """INSERT INTO users (role_id, email, password_hash, name, status)
           SELECT id, %s, %s, %s, 'ACTIVE' FROM roles WHERE code = 'USER'""",
        (email, password_hash, name),
    )


def create_session(session_id: str, user_id: int, expires_at: datetime) -> None:
    execute_query(
        "INSERT INTO auth_sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
        (session_id, user_id, expires_at),
    )


def find_active_session(session_id: str, user_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT id FROM auth_sessions
           WHERE id = %s AND user_id = %s AND revoked_at IS NULL
             AND expires_at > UTC_TIMESTAMP(6)""",
        (session_id, user_id),
        one=True,
    )
    return row if isinstance(row, dict) else None


def touch_login(user_id: int, session_id: str) -> None:
    execute_query("UPDATE users SET last_login_at = UTC_TIMESTAMP(6) WHERE id = %s", (user_id,))
    execute_query(
        "UPDATE auth_sessions SET last_used_at = UTC_TIMESTAMP(6) WHERE id = %s",
        (session_id,),
    )


def revoke_session(session_id: str) -> None:
    execute_query(
        "UPDATE auth_sessions SET revoked_at = UTC_TIMESTAMP(6) WHERE id = %s AND revoked_at IS NULL",
        (session_id,),
    )


def update_profile(
    user_id: int,
    name: str,
    email: str,
    password_hash: str | None = None,
) -> None:
    if password_hash:
        execute_query(
            "UPDATE users SET name = %s, email = %s, password_hash = %s WHERE id = %s AND deleted_at IS NULL",
            (name, email, password_hash, user_id),
        )
    else:
        execute_query(
            "UPDATE users SET name = %s, email = %s WHERE id = %s AND deleted_at IS NULL",
            (name, email, user_id),
        )


def set_profile_file(user_id: int, file_id: int | None) -> None:
    execute_query(
        "UPDATE users SET profile_file_id = %s WHERE id = %s AND deleted_at IS NULL",
        (file_id, user_id),
    )
