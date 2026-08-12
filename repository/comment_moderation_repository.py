"""Administrator comment moderation queries and transactional state changes."""

from typing import Any

import pymysql

from common.db import engine, fetch_query


def find_all(
    page: int, page_size: int, keyword: str | None, status: str | None,
    comment_type: str | None, board_id: int | None, author_id: int | None,
) -> tuple[list[dict[str, Any]], int]:
    where = "WHERE 1 = 1"
    params: list[Any] = []
    if keyword:
        where += " AND (c.content LIKE %s OR u.name LIKE %s OR u.email LIKE %s OR b.title LIKE %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern, pattern, pattern))
    if status:
        where += " AND c.status = %s"
        params.append(status)
    if comment_type == "COMMENT":
        where += " AND c.parent_comment_id IS NULL"
    elif comment_type == "REPLY":
        where += " AND c.parent_comment_id IS NOT NULL"
    if board_id is not None:
        where += " AND c.board_id = %s"
        params.append(board_id)
    if author_id is not None:
        where += " AND c.author_id = %s"
        params.append(author_id)

    joins = """FROM board_comments c
        JOIN boards b ON b.id = c.board_id
        JOIN users u ON u.id = c.author_id
        LEFT JOIN board_comments p ON p.id = c.parent_comment_id
        LEFT JOIN users m ON m.id = c.moderated_by"""
    count = fetch_query(f"SELECT COUNT(*) AS total {joins} {where}", tuple(params), one=True)
    rows = fetch_query(
        f"""SELECT c.id, c.board_id AS boardId, b.title AS boardTitle,
                   c.parent_comment_id AS parentId, p.content AS parentContent,
                   c.author_id AS authorId, u.name AS authorName, u.email AS authorEmail,
                   c.content, c.emoticon, c.status, c.created_at AS createdAt,
                   c.updated_at AS updatedAt, c.deleted_at AS deletedAt,
                   c.moderated_by AS moderatedBy, m.name AS moderatorName,
                   c.moderated_at AS moderatedAt, c.moderation_reason AS moderationReason,
                   (SELECT COUNT(*) FROM board_comments r WHERE r.parent_comment_id = c.id) AS replyCount
            {joins} {where}
            ORDER BY c.created_at DESC, c.id DESC LIMIT %s OFFSET %s""",
        (*params, page_size, (page - 1) * page_size),
    )
    total = int(count["total"]) if isinstance(count, dict) else 0
    return (rows if isinstance(rows, list) else []), total


def find_context(comment_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT c.id, c.board_id AS boardId, b.title AS boardTitle,
                  c.parent_comment_id AS parentId, p.content AS parentContent,
                  c.author_id AS authorId, u.name AS authorName, u.email AS authorEmail,
                  c.content, c.status, c.created_at AS createdAt,
                  c.moderated_at AS moderatedAt, c.moderation_reason AS moderationReason
           FROM board_comments c
           JOIN boards b ON b.id = c.board_id
           JOIN users u ON u.id = c.author_id
           LEFT JOIN board_comments p ON p.id = c.parent_comment_id
           WHERE c.id = %s""",
        (comment_id,), one=True,
    )
    return row if isinstance(row, dict) else None


def find_history(comment_id: int) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT l.id, l.action, l.previous_status AS previousStatus,
                  l.next_status AS nextStatus, l.reason,
                  l.created_at AS createdAt, l.moderator_id AS moderatorId,
                  u.name AS moderatorName
           FROM comment_moderation_logs l
           LEFT JOIN users u ON u.id = l.moderator_id
           WHERE l.comment_id = %s ORDER BY l.created_at DESC, l.id DESC""",
        (comment_id,),
    )
    return rows if isinstance(rows, list) else []


def find_recent_by_author(author_id: int, exclude_id: int, limit: int = 8) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT c.id, c.board_id AS boardId, b.title AS boardTitle,
                  c.content, c.status, c.created_at AS createdAt
           FROM board_comments c JOIN boards b ON b.id = c.board_id
           WHERE c.author_id = %s AND c.id <> %s
           ORDER BY c.created_at DESC LIMIT %s""",
        (author_id, exclude_id, limit),
    )
    return rows if isinstance(rows, list) else []


def moderate(comment_id: int, moderator_id: int, action: str, reason: str) -> bool:
    target_status = {"HIDE": "HIDDEN", "RESTORE": "ACTIVE", "DELETE": "DELETED"}[action]
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT status FROM board_comments WHERE id = %s FOR UPDATE", (comment_id,))
            row = cursor.fetchone()
            if not row:
                connection.rollback()
                return False
            previous = row["status"]
            deleted_sql = "UTC_TIMESTAMP(6)" if target_status == "DELETED" else "NULL"
            cursor.execute(
                f"""UPDATE board_comments SET status = %s, deleted_at = {deleted_sql},
                           moderated_by = %s, moderated_at = UTC_TIMESTAMP(6),
                           moderation_reason = %s, updated_at = UTC_TIMESTAMP(6)
                    WHERE id = %s""",
                (target_status, moderator_id, reason, comment_id),
            )
            cursor.execute(
                """INSERT INTO comment_moderation_logs
                   (comment_id, moderator_id, action, previous_status, next_status, reason)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (comment_id, moderator_id, action, previous, target_status, reason),
            )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
