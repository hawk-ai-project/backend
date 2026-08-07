"""질문 도메인의 직접 SQL 저장소."""

from datetime import datetime
from typing import Any

from common.db import execute_query, fetch_query


def find_all() -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT id, subject, content, create_date
        FROM question
        ORDER BY create_date DESC, id DESC"""
    )
    return rows if isinstance(rows, list) else []


def find_by_id(question_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT id, subject, content, create_date
        FROM question
        WHERE id = %s""",
        (question_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def create(subject: str, content: str) -> int:
    return execute_query(
        """INSERT INTO question (subject, content, create_date)
        VALUES (%s, %s, %s)""",
        (subject, content, datetime.now()),
    )


def update(question_id: int, subject: str, content: str) -> int:
    return execute_query(
        """UPDATE question
        SET subject = %s, content = %s
        WHERE id = %s""",
        (subject, content, question_id),
    )


def delete(question_id: int) -> int:
    return execute_query("DELETE FROM question WHERE id = %s", (question_id,))
