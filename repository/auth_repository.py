"""Database access for users and authentication sessions."""

from datetime import datetime
from typing import Any

from common.db import execute_query, fetch_query, engine


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


def create_session(
    session_id: str,
    user_id: int,
    expires_at: datetime,
    user_agent: str | None = None,
    ip_address: str | None = None,
    refresh_token_hash: str | None = None,
) -> None:
    execute_query(
        """INSERT INTO auth_sessions
           (id, user_id, expires_at, user_agent, ip_address, refresh_token_hash)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (session_id, user_id, expires_at, user_agent, ip_address, refresh_token_hash),
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


def rotate_refresh_token(
    current_hash: str,
    next_hash: str,
    expires_at: datetime,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any] | None:
    """Atomically consume a refresh token so replayed tokens cannot be reused."""
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE auth_sessions
                   SET refresh_token_hash = %s, expires_at = %s,
                       last_used_at = UTC_TIMESTAMP(6),
                       user_agent = COALESCE(%s, user_agent),
                       ip_address = COALESCE(%s, ip_address)
                   WHERE refresh_token_hash = %s AND revoked_at IS NULL
                     AND expires_at > UTC_TIMESTAMP(6)""",
                (next_hash, expires_at, user_agent, ip_address, current_hash),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            cursor.execute(
                """SELECT s.id, s.user_id AS userId
                   FROM auth_sessions s WHERE s.refresh_token_hash = %s""",
                (next_hash,),
            )
            row = cursor.fetchone()
        connection.commit()
        return {"id": row[0], "userId": row[1]} if row else None
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def revoke_by_refresh_hash(refresh_hash: str) -> bool:
    return execute_query(
        """UPDATE auth_sessions SET revoked_at = UTC_TIMESTAMP(6), refresh_token_hash = NULL
           WHERE refresh_token_hash = %s AND revoked_at IS NULL""",
        (refresh_hash,),
    ) > 0


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
