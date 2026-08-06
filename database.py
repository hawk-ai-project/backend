# database.py
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from typing import Dict, Any, List, Optional
from fastapi import Request, Depends

# DB 접속 URL 설정: mysql+pymysql://[계정]:[비밀번호]@[아이피]:[포트]/[DB이름]
# SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:20260804@localhost:3306/cctv_db"
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://cctv_user:cctv1234!@192.168.0.151:3306/cctv_db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_recycle=3600  # MySQL 커넥션 끊김 방지 옵션
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI 라우터에서 사용할 DB 세션 생성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_sql(request: Request):
    """app.state.sql에서 '파일명.쿼리명' 키에 해당하는 text() 쿼리를 안전하게 반환"""

    def _get_query(query_key: str) -> text:
        sql_map = request.app.state.sql
        query = sql_map.get(query_key)

        if not query:
            raise KeyError(f"등록되지 않은 SQL 쿼리 키입니다: {query_key}")
        return query

    return _get_query


class DatabaseContext:
    def __init__(self, db: Session, sql_map: dict):
        self.db = db
        self.sql_map = sql_map

    def _get_query(self, query_key: str) -> text:
        """쿼리 키 검증 및 text 객체 반환"""
        query = self.sql_map.get(query_key)
        if not query:
            raise KeyError(f"등록되지 않은 SQL 쿼리 키입니다: {query_key}")
        return query

    def execute_sql(self, query_key: str, params: Optional[Dict[str, Any]] = None):
        """기본 SQL 실행 (CUD 작업 또는 커스텀 핸들링용)"""
        query = self._get_query(query_key)
        return self.db.execute(query, params or {})

    def select_all(self, query_key: str, params: Optional[Dict[str, Any]] = None) -> List[dict]:
        """다건 조회 헬퍼: 결과를 list[dict] 형태로 즉시 반환"""
        result = self.execute_sql(query_key, params)
        return [dict(row._mapping) for row in result]

    def select_one(self, query_key: str, params: Optional[Dict[str, Any]] = None) -> Optional[dict]:
        """단건 조회 헬퍼: 결과를 dict 형태로 즉시 반환 (없으면 None)"""
        result = self.execute_sql(query_key, params)
        row = result.fetchone()
        return dict(row._mapping) if row else None


def get_db_ctx(request: Request, db: Session = Depends(get_db)) -> DatabaseContext:
    """Session과 app.state.sql을 하나로 묶어서 반환하는 Dependency"""
    return DatabaseContext(db=db, sql_map=request.app.state.sql)