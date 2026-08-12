"""게시판 댓글과 대댓글을 저장하는 직접 SQL 저장소."""

from typing import Any

from common.db import execute_query, fetch_query


_COMMENT_SELECT = """
SELECT c.id, c.board_id AS boardId, c.parent_comment_id AS parentId,
       c.content, c.emoticon, c.created_at AS createdAt, c.updated_at AS updatedAt,
       u.id AS authorId, u.name AS authorName, u.profile_file_id AS authorProfileFileId
FROM board_comments c
JOIN users u ON u.id = c.author_id
"""


def _to_comment(row: dict[str, Any]) -> dict[str, Any]:
    profile_file_id = row.pop("authorProfileFileId", None)
    author_id = int(row.pop("authorId"))
    row["author"] = {
        "id": author_id,
        "name": row.pop("authorName"),
        "profileImageUrl": (
            f"/api/boards/authors/{author_id}/profile-image" if profile_file_id else None
        ),
    }
    row["replies"] = []
    return row


def board_exists(board_id: int) -> bool:
    row = fetch_query(
        "SELECT id FROM boards WHERE id = %s AND deleted_at IS NULL AND status = 'PUBLISHED'",
        (board_id,),
        one=True,
    )
    return isinstance(row, dict)


def find_all(board_id: int) -> list[dict[str, Any]]:
    rows = fetch_query(
        f"""{_COMMENT_SELECT}
        WHERE c.board_id = %s AND c.deleted_at IS NULL
        ORDER BY COALESCE(c.parent_comment_id, c.id) ASC, c.parent_comment_id IS NOT NULL ASC, c.created_at ASC, c.id ASC""",
        (board_id,),
    )
    comments = [_to_comment(row) for row in rows] if isinstance(rows, list) else []
    roots: list[dict[str, Any]] = []
    root_by_id: dict[int, dict[str, Any]] = {}
    for comment in comments:
        if comment["parentId"] is None:
            roots.append(comment)
            root_by_id[int(comment["id"])] = comment
        elif int(comment["parentId"]) in root_by_id:
            root_by_id[int(comment["parentId"])]["replies"].append(comment)
    return roots


def find_by_id(comment_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        f"{_COMMENT_SELECT} WHERE c.id = %s AND c.deleted_at IS NULL",
        (comment_id,),
        one=True,
    )
    return _to_comment(row) if isinstance(row, dict) else None


def find_parent(board_id: int, parent_id: int) -> dict[str, Any] | None:
    return fetch_query(
        """SELECT id, parent_comment_id AS parentId FROM board_comments
           WHERE id = %s AND board_id = %s AND deleted_at IS NULL""",
        (parent_id, board_id),
        one=True,
    )


def create(board_id: int, author_id: int, data: dict[str, Any]) -> int:
    return execute_query(
        """INSERT INTO board_comments (board_id, author_id, parent_comment_id, content, emoticon)
           VALUES (%s, %s, %s, %s, %s)""",
        (board_id, author_id, data.get("parentId"), data.get("content", ""), data.get("emoticon")),
    )


def update(comment_id: int, data: dict[str, Any]) -> bool:
    return execute_query(
        """UPDATE board_comments
           SET content = %s, emoticon = %s, updated_at = UTC_TIMESTAMP(6)
           WHERE id = %s AND deleted_at IS NULL""",
        (data.get("content", ""), data.get("emoticon"), comment_id),
    ) > 0


def soft_delete(comment_id: int) -> bool:
    return execute_query(
        """UPDATE board_comments SET deleted_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
           WHERE id = %s AND deleted_at IS NULL""",
        (comment_id,),
    ) > 0
