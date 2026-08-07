"""FastAPI에서 사용하는 MySQL 직접 SQL 연결 유틸리티."""

from collections.abc import Generator, Mapping, Sequence
from typing import Any

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import PoolProxiedConnection

from config import settings


DATABASE_URL = settings.database_url


# SQLAlchemy의 ORM 기능은 사용하지 않고 커넥션 풀만 사용한다.
engine: Engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=500,
    pool_pre_ping=True,
)

QueryArgs = Sequence[Any] | Mapping[str, Any]


def get_db() -> Generator[PoolProxiedConnection, None, None]:
    """FastAPI ``Depends``에 요청별 DB 연결을 제공한다.

    사용 예::

        @router.get("/items")
        def get_items(db = Depends(get_db)):
            with db.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM items")
                return cursor.fetchall()
    """
    connection = engine.raw_connection()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def execute_query(
    sql: str,
    args: QueryArgs = (),
) -> int:
    """연결을 직접 관리하며 INSERT, UPDATE, DELETE를 실행한다."""
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, args)
            connection.commit()
            return int(cursor.lastrowid or cursor.rowcount)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_query(
    sql: str,
    args: QueryArgs = (),
    *,
    one: bool = False,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """연결을 직접 관리하며 SELECT 결과를 딕셔너리로 반환한다."""
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, args)
            if one:
                return cursor.fetchone()
            return list(cursor.fetchall())
    finally:
        connection.close()
