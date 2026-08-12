"""Read-only database queries used by the administrator console."""

from typing import Any

from common.db import execute_query, fetch_query


_USER_SELECT = """
SELECT u.id, u.name, u.email, r.code AS role, u.status,
       u.profile_file_id AS profileFileId,
       u.last_login_at AS lastLoginAt, u.created_at AS createdAt
FROM users u
JOIN roles r ON r.id = u.role_id
"""


def find_users(page: int, page_size: int, keyword: str | None) -> tuple[list[dict[str, Any]], int]:
    where = "WHERE u.deleted_at IS NULL"
    params: list[Any] = []
    if keyword:
        where += " AND (u.name LIKE %s OR u.email LIKE %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern))

    count_row = fetch_query(
        f"SELECT COUNT(*) AS total FROM users u {where}", tuple(params), one=True
    )
    rows = fetch_query(
        f"""{_USER_SELECT} {where}
        ORDER BY u.created_at DESC, u.id DESC LIMIT %s OFFSET %s""",
        (*params, page_size, (page - 1) * page_size),
    )
    total = int(count_row["total"]) if isinstance(count_row, dict) else 0
    return (rows if isinstance(rows, list) else []), total


def dashboard_stats() -> dict[str, Any]:
    row = fetch_query(
        """SELECT
          (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL) AS totalUsers,
          (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND status = 'ACTIVE') AS activeUsers,
          (SELECT COUNT(*) FROM users u JOIN roles r ON r.id = u.role_id
             WHERE u.deleted_at IS NULL AND r.code = 'ADMIN') AS adminUsers,
          (SELECT COUNT(*) FROM users WHERE deleted_at IS NULL
             AND created_at >= DATE_FORMAT(UTC_TIMESTAMP(), '%%Y-%%m-01')) AS newUsersThisMonth,
          (SELECT COUNT(*) FROM boards WHERE deleted_at IS NULL AND status = 'PUBLISHED') AS publishedBoards,
          (SELECT COUNT(*) FROM inspections WHERE deleted_at IS NULL) AS totalInspections""",
        one=True,
    )
    return row if isinstance(row, dict) else {}


def recent_users(limit: int = 5) -> list[dict[str, Any]]:
    rows = fetch_query(
        f"""{_USER_SELECT}
        WHERE u.deleted_at IS NULL
        ORDER BY u.created_at DESC, u.id DESC LIMIT %s""",
        (limit,),
    )
    return rows if isinstance(rows, list) else []


def find_roles() -> list[dict[str, Any]]:
    rows = fetch_query(
        "SELECT code, name, description FROM roles ORDER BY id"
    )
    return rows if isinstance(rows, list) else []


def count_admins() -> int:
    row = fetch_query(
        """SELECT COUNT(*) AS total FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.deleted_at IS NULL AND u.status = 'ACTIVE' AND r.code = 'ADMIN'""",
        one=True,
    )
    return int(row["total"]) if isinstance(row, dict) else 0


def update_user_role(user_id: int, role_code: str) -> bool:
    affected = execute_query(
        """UPDATE users u
        JOIN roles r ON r.code = %s
        SET u.role_id = r.id
        WHERE u.id = %s AND u.deleted_at IS NULL""",
        (role_code, user_id),
    )
    return affected > 0


_ADMIN_BOARD_SELECT = """
SELECT b.id, b.title, bc.name AS category,
       u.id AS authorId, u.name AS authorName,
       b.status, b.is_notice AS isNotice, b.view_count AS viewCount,
       b.published_at AS publishedAt, b.created_at AS createdAt,
       b.updated_at AS updatedAt
FROM boards b
JOIN board_categories bc ON bc.id = b.category_id
JOIN users u ON u.id = b.author_id
"""


def find_boards(
    page: int,
    page_size: int,
    keyword: str | None,
    status: str | None,
) -> tuple[list[dict[str, Any]], int]:
    where = "WHERE b.deleted_at IS NULL"
    params: list[Any] = []
    if keyword:
        where += " AND (b.title LIKE %s OR u.name LIKE %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern))
    if status:
        where += " AND b.status = %s"
        params.append(status)

    count_row = fetch_query(
        f"""SELECT COUNT(*) AS total FROM boards b
        JOIN users u ON u.id = b.author_id {where}""",
        tuple(params),
        one=True,
    )
    rows = fetch_query(
        f"""{_ADMIN_BOARD_SELECT} {where}
        ORDER BY b.created_at DESC, b.id DESC LIMIT %s OFFSET %s""",
        (*params, page_size, (page - 1) * page_size),
    )
    total = int(count_row["total"]) if isinstance(count_row, dict) else 0
    return (rows if isinstance(rows, list) else []), total


def update_board_status(board_id: int, status: str) -> bool:
    affected = execute_query(
        """UPDATE boards
        SET status = %s,
            published_at = CASE
                WHEN %s = 'PUBLISHED' THEN COALESCE(published_at, UTC_TIMESTAMP(6))
                ELSE published_at
            END,
            updated_at = UTC_TIMESTAMP(6)
        WHERE id = %s AND deleted_at IS NULL""",
        (status, status, board_id),
    )
    return affected > 0


def soft_delete_board(board_id: int) -> bool:
    affected = execute_query(
        """UPDATE boards
        SET deleted_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
        WHERE id = %s AND deleted_at IS NULL""",
        (board_id,),
    )
    return affected > 0


def security_overview() -> dict[str, Any]:
    row = fetch_query(
        """SELECT
          (SELECT COUNT(*) FROM auth_sessions
             WHERE revoked_at IS NULL AND expires_at > UTC_TIMESTAMP(6)) AS activeSessions,
          (SELECT COUNT(DISTINCT user_id) FROM auth_sessions
             WHERE revoked_at IS NULL AND expires_at > UTC_TIMESTAMP(6)) AS activeUsers,
          (SELECT COUNT(*) FROM auth_sessions
             WHERE revoked_at IS NULL AND expires_at > UTC_TIMESTAMP(6)
               AND expires_at <= UTC_TIMESTAMP(6) + INTERVAL 1 HOUR) AS expiringSoon,
          (SELECT COUNT(*) FROM auth_sessions
             WHERE revoked_at >= UTC_TIMESTAMP(6) - INTERVAL 24 HOUR) AS revoked24h,
          (SELECT COUNT(*) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP(6) - INTERVAL 24 HOUR
               AND category = 'AUTH' AND action = 'LOGIN' AND outcome <> 'SUCCESS') AS failedLogins24h,
          (SELECT COUNT(*) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP(6) - INTERVAL 24 HOUR
               AND outcome = 'DENIED') AS deniedRequests24h""",
        one=True,
    )
    return row if isinstance(row, dict) else {}


def find_sessions(
    page: int, page_size: int, keyword: str | None, session_status: str | None,
) -> tuple[list[dict[str, Any]], int]:
    status_expression = """CASE WHEN s.revoked_at IS NOT NULL THEN 'REVOKED'
        WHEN s.expires_at <= UTC_TIMESTAMP(6) THEN 'EXPIRED' ELSE 'ACTIVE' END"""
    where = "WHERE 1 = 1"
    params: list[Any] = []
    if keyword:
        where += " AND (u.name LIKE %s OR u.email LIKE %s OR s.ip_address LIKE %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern, pattern))
    if session_status:
        where += f" AND {status_expression} = %s"
        params.append(session_status)
    count = fetch_query(
        f"""SELECT COUNT(*) AS total FROM auth_sessions s
            JOIN users u ON u.id = s.user_id {where}""",
        tuple(params), one=True,
    )
    rows = fetch_query(
        f"""SELECT s.id, u.id AS userId, u.name AS userName, u.email AS userEmail,
                   r.code AS userRole, s.ip_address AS ipAddress,
                   s.user_agent AS userAgent, {status_expression} AS status,
                   s.created_at AS createdAt, s.last_used_at AS lastUsedAt,
                   s.expires_at AS expiresAt, s.revoked_at AS revokedAt
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            JOIN roles r ON r.id = u.role_id
            {where}
            ORDER BY s.created_at DESC LIMIT %s OFFSET %s""",
        (*params, page_size, (page - 1) * page_size),
    )
    total = int(count["total"]) if isinstance(count, dict) else 0
    return (rows if isinstance(rows, list) else []), total


def revoke_session_by_id(session_id: str) -> bool:
    return execute_query(
        """UPDATE auth_sessions SET revoked_at = UTC_TIMESTAMP(6)
           WHERE id = %s AND revoked_at IS NULL AND expires_at > UTC_TIMESTAMP(6)""",
        (session_id,),
    ) > 0


def revoke_all_sessions(exclude_session_id: str | None = None) -> int:
    where = "WHERE revoked_at IS NULL AND expires_at > UTC_TIMESTAMP(6)"
    params: tuple[Any, ...] = ()
    if exclude_session_id:
        where += " AND id <> %s"
        params = (exclude_session_id,)
    return execute_query(
        f"UPDATE auth_sessions SET revoked_at = UTC_TIMESTAMP(6) {where}", params,
    )
