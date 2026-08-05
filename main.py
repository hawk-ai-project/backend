from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import engine, DatabaseContext, get_db_ctx
from domain.question import question_router
from sql_loader import load_all_sqls

from fastapi.responses import HTMLResponse  # 추가됨

# 쿼리를 수행해야 하는 .py파일인 경우 아래 Depends, get_sql 추가
# from fastapi import FastAPI, Depends
# from database import engine, get_db, get_sql

import models

# 앱 시작 시 MySQL에 테이블 자동 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hawk-AI API Server")

# 1. 앱 시작 시 전역 상태(app.state)에 1회 등록
app.state.sql = load_all_sqls("sql")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.0.151:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://192.168.0.151:5174",
]

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(question_router.router)


# ---------------------------------------------------------
# 서버 구동 상태 확인용 루트 엔드포인트
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTMLResponse(
        content=r"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hawk-AI API Server</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #0f172a;
                color: #f8fafc;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background-color: #1e293b;
                padding: 2.5rem;
                border-radius: 1rem;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                text-align: center;
                max-width: 420px;
                width: 100%;
                border: 1px solid #334155;
            }
            .status-badge {
                display: inline-block;
                background-color: #10b981;
                color: #ffffff;
                padding: 0.3rem 0.8rem;
                border-radius: 9999px;
                font-size: 0.875rem;
                font-weight: 600;
                margin-bottom: 1rem;
            }
            h1 {
                margin: 0 0 0.5rem 0;
                font-size: 1.75rem;
                color: #38bdf8;
            }
            p {
                color: #94a3b8;
                margin-bottom: 2rem;
                font-size: 0.95rem;
            }
            .btn {
                display: inline-block;
                background-color: #3b82f6;
                color: white;
                text-decoration: none;
                padding: 0.75rem 1.5rem;
                border-radius: 0.5rem;
                font-weight: 600;
                transition: background-color 0.2s;
            }
            .btn:hover {
                background-color: #2563eb;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <span class="status-badge">● ONLINE</span>
            <h1>Hawk-AI API Server</h1>
            <p>백엔드 서버가 성공적으로 작동 중입니다.</p>
            <a href="/docs" class="btn">Swagger API 문서 바로가기</a>
        </div>
    </body>
    </html>
    """
    )

# ---------------------------------------------------------
# 기존 기본 엔드포인트 (주석 처리)
# ---------------------------------------------------------
# @app.get("/")
# def index():
#     return {"message": "잘왔다 FastAPI Server에!!"}


# @app.get("/hello")
# def hello():
#     return {"message": "웰컴 또 왔네"}


# ---------------------------------------------------------
# Raw SQL API 샘플 (DatabaseContext 및 Param 활용)
# ---------------------------------------------------------

# 1) 파라미터 없는 전체/활성 메뉴 목록 조회
@app.get("/api/menu/list")
def get_menu_list(ctx: DatabaseContext = Depends(get_db_ctx)):
    result = ctx.execute_sql("menu.get_active_menus")
    return [dict(row._mapping) for row in result]

    # select_all 을 사용하는 경우
    # return ctx.select_all("menu.get_active_menus")


# 2) Path/Query 파라미터를 받아 단건 조회
@app.get("/api/menu/{menu_id}")
def get_menu_detail(menu_id: int, ctx: DatabaseContext = Depends(get_db_ctx)):
    # 딕셔너리 형태 {"menu_id": menu_id}로 파라미터 전달
    params = {"menu_id": menu_id}
    menu = ctx.select_one("menu.get_menu_by_id", params)

    if not menu:
        raise HTTPException(
            status_code=404, detail="해당 메뉴를 찾을 수 없습니다."
        )
    return menu


# 3) Body 파라미터(JSON)를 받아 등록/수정 (CUD 및 커밋)
@app.post("/api/menu")
def create_menu(menu_data: dict, ctx: DatabaseContext = Depends(get_db_ctx)):
    """클라이언트(Postman/프론트엔드)에서 전달받는 JSON 예시:

    {
        "name": "시스템 관리",
        "path": "/system",
        "icon": "settings",
        "is_use": 1,
        "sort_order": 5,
        "parent_id": None,
        "menu_type": "GROUP",
        "description": "최상위 관리자 전용 메뉴"
    }
    """
    # menu_data 딕셔너리가 SQL 파일의 :name, :path 등의 변수와 1:1 매핑됨
    ctx.execute_sql("menu.insert_menu", menu_data)
    ctx.db.commit()  # 데이터 변경 발생 시 커밋 실행

    return {"message": "메뉴가 성공적으로 등록되었습니다."}

