"""게시판 도메인의 직접 SQL 저장소."""

import json
from typing import Any

from common.db import fetch_query


_BOARD_SELECT = """
SELECT b.id, bc.name AS category, b.title, b.summary, b.content,
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
) -> tuple[list[dict[str, Any]], int]:
    """공개 게시글 목록과 전체 건수를 페이지 단위로 조회한다."""
    where = "WHERE b.deleted_at IS NULL AND b.status = 'PUBLISHED'"
    params: list[Any] = []
    if keyword:
        where += " AND (b.title LIKE %s OR b.content LIKE %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern))

    count = fetch_query(
        f"SELECT COUNT(*) AS total FROM boards b {where}",
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


def find_by_id(board_id: int) -> dict[str, Any] | None:
    """식별자에 해당하는 공개 게시글 한 건을 조회한다."""
    row = fetch_query(
        f"""{_BOARD_SELECT}
        WHERE b.id = %s
          AND b.deleted_at IS NULL
          AND b.status = 'PUBLISHED'""",
        (board_id,),
        one=True,
    )
    return _to_board(row) if isinstance(row, dict) else None
