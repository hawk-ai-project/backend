"""게시판 도메인의 직접 SQL 저장소."""

import json
from typing import Any

import pymysql

from common.db import engine, execute_query, fetch_query


class InvalidCategoryError(Exception):
    pass


_BOARD_SELECT = """
SELECT b.id, b.category_id AS categoryId, bc.name AS category, b.title, b.summary, b.content,
       b.created_at AS createdAt, b.updated_at AS updatedAt,
       b.view_count AS viewCount, b.thumbnail_url AS thumbnailUrl,
       u.id AS authorId, u.name AS authorName,
       COALESCE(
           (SELECT JSON_ARRAYAGG(t.name)
            FROM board_tags bt
            JOIN tags t ON t.id = bt.tag_id
            WHERE bt.board_id = b.id),
           JSON_ARRAY()
       ) AS tags
FROM boards b
JOIN board_categories bc ON bc.id = b.category_id
JOIN users u ON u.id = b.author_id
"""


def _to_board(row: dict[str, Any]) -> dict[str, Any]:
    """데이터베이스 조회 결과를 게시글 응답 구조로 변환한다."""
    tags = row.pop("tags", [])
    if isinstance(tags, str):
        tags = json.loads(tags)
    row["tags"] = tags or []
    row["author"] = {
        "id": row.pop("authorId"),
        "name": row.pop("authorName"),
    }
    return row


def find_all(
    page: int,
    page_size: int,
    keyword: str | None = None,
    category: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """공개 게시글 목록과 전체 건수를 페이지 단위로 조회한다."""
    where = "WHERE b.deleted_at IS NULL AND b.status = 'PUBLISHED'"
    params: list[Any] = []
    if keyword:
        where += " AND (b.title LIKE %s OR b.content LIKE %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern))
    if category:
        where += " AND bc.name = %s"
        params.append(category)

    count = fetch_query(
        f"SELECT COUNT(*) AS total FROM boards b JOIN board_categories bc ON bc.id = b.category_id {where}",
        tuple(params),
        one=True,
    )
    total = int(count["total"]) if isinstance(count, dict) else 0
    rows = fetch_query(
        f"""{_BOARD_SELECT} {where}
        ORDER BY b.is_notice DESC, b.published_at DESC, b.id DESC
        LIMIT %s OFFSET %s""",
        (*params, page_size, (page - 1) * page_size),
    )
    items = [_to_board(row) for row in rows] if isinstance(rows, list) else []
    return items, total


def find_by_id(board_id: int, *, increment_view: bool = False) -> dict[str, Any] | None:
    """식별자에 해당하는 공개 게시글 한 건을 조회한다."""
    if increment_view:
        execute_query(
            """UPDATE boards SET view_count = view_count + 1
               WHERE id = %s AND deleted_at IS NULL AND status = 'PUBLISHED'""",
            (board_id,),
        )
    row = fetch_query(
        f"""{_BOARD_SELECT}
        WHERE b.id = %s
          AND b.deleted_at IS NULL
          AND b.status = 'PUBLISHED'""",
        (board_id,),
        one=True,
    )
    return _to_board(row) if isinstance(row, dict) else None


def find_author_id(board_id: int) -> int | None:
    row = fetch_query(
        """SELECT author_id FROM boards
           WHERE id = %s AND deleted_at IS NULL AND status = 'PUBLISHED'""",
        (board_id,), one=True,
    )
    return int(row["author_id"]) if isinstance(row, dict) else None


def _category_exists(cursor, category_id: int) -> bool:
    cursor.execute(
        "SELECT id FROM board_categories WHERE id = %s AND is_active = TRUE",
        (category_id,),
    )
    return cursor.fetchone() is not None


def _replace_tags(cursor, board_id: int, tags: list[str]) -> None:
    cursor.execute("DELETE FROM board_tags WHERE board_id = %s", (board_id,))
    for sort_order, name in enumerate(tags):
        normalized = "".join(name.lower().split())
        cursor.execute(
            """INSERT INTO tags (name, normalized_name) VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)""",
            (name, normalized),
        )
        tag_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO board_tags (board_id, tag_id, sort_order) VALUES (%s, %s, %s)",
            (board_id, tag_id, sort_order),
        )


def create(data: dict[str, Any], author_id: int) -> int:
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            if not _category_exists(cursor, data["categoryId"]):
                raise InvalidCategoryError
            cursor.execute(
                """INSERT INTO boards
                   (category_id, author_id, title, summary, content, status, published_at)
                   VALUES (%s, %s, %s, %s, %s, 'PUBLISHED', UTC_TIMESTAMP(6))""",
                (data["categoryId"], author_id, data["title"], data.get("summary"), data["content"]),
            )
            board_id = int(cursor.lastrowid)
            _replace_tags(cursor, board_id, data.get("tags", []))
        connection.commit()
        return board_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update(board_id: int, data: dict[str, Any]) -> None:
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            if "categoryId" in data and not _category_exists(cursor, data["categoryId"]):
                raise InvalidCategoryError
            columns = {
                "categoryId": "category_id", "title": "title",
                "summary": "summary", "content": "content",
            }
            assignments = [f"{columns[key]} = %s" for key in columns if key in data]
            values = [data[key] for key in columns if key in data]
            if assignments:
                cursor.execute(
                    f"UPDATE boards SET {', '.join(assignments)}, updated_at = UTC_TIMESTAMP(6) "
                    "WHERE id = %s AND deleted_at IS NULL AND status = 'PUBLISHED'",
                    (*values, board_id),
                )
            if "tags" in data:
                _replace_tags(cursor, board_id, data["tags"])
                if not assignments:
                    cursor.execute(
                        "UPDATE boards SET updated_at = UTC_TIMESTAMP(6) WHERE id = %s",
                        (board_id,),
                    )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def soft_delete(board_id: int) -> bool:
    affected = execute_query(
        """UPDATE boards SET deleted_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
           WHERE id = %s AND deleted_at IS NULL AND status = 'PUBLISHED'""",
        (board_id,),
    )
    return affected > 0
