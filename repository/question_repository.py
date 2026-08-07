"""질문 도메인의 직접 SQL 저장소."""

from datetime import datetime
from typing import Any

from common.db import execute_query, fetch_query


def find_all() -> list[dict[str, Any]]:
    """모든 질문을 최신순으로 조회한다."""
    rows = fetch_query(
        """SELECT id, subject, content, create_date
        FROM question
        ORDER BY create_date DESC, id DESC"""
    )
    return rows if isinstance(rows, list) else []


def find_by_id(question_id: int) -> dict[str, Any] | None:
    """식별자에 해당하는 질문 한 건을 조회한다."""
    row = fetch_query(
        """SELECT id, subject, content, create_date
        FROM question
        WHERE id = %s""",
        (question_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def create(subject: str, content: str) -> int:
    """새 질문을 등록하고 생성된 식별자를 반환한다."""
    return execute_query(
        """INSERT INTO question (subject, content, create_date)
        VALUES (%s, %s, %s)""",
        (subject, content, datetime.now()),
    )


def update(question_id: int, subject: str, content: str) -> int:
    """식별자에 해당하는 질문의 제목과 내용을 수정한다."""
    return execute_query(
        """UPDATE question
        SET subject = %s, content = %s
        WHERE id = %s""",
        (subject, content, question_id),
    )


def delete(question_id: int) -> int:
    """식별자에 해당하는 질문을 삭제한다."""
    return execute_query("DELETE FROM question WHERE id = %s", (question_id,))
