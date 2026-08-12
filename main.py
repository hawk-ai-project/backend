from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from controller import admin_controller, analytics_controller, analytics_insight_controller, auth_controller, board_controller, chat_controller, file_controller, hokeytoon_controller, inspection_controller, menu_controller, question_controller
from service.auth_service import AuthError
from service import activity_service

from fastapi.responses import HTMLResponse  # 추가됨

app = FastAPI(title="Hawk-AI API Server")
app.add_exception_handler(AuthError, auth_controller.auth_error_response)

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://192.168.0.172:3000",
    "http://192.168.0.172:3001",
    "http://192.168.0.151:3000",
    "http://192.168.0.173:3000",
    "http://192.168.0.173:3001",
]

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def activity_monitoring(request: Request, call_next):
    """Record API activity without storing bodies, tokens, or query values."""
    supplied_request_id = request.headers.get("X-Request-ID")
    try:
        request_id = str(UUID(supplied_request_id)) if supplied_request_id else str(uuid4())
    except (ValueError, TypeError):
        request_id = str(uuid4())
    request.state.request_id = request_id
    started = perf_counter()
    status_code = 500
    response = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        if request.url.path.startswith("/api"):
            route = request.scope.get("route")
            activity_service.record_http_request(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                route_template=getattr(route, "path", None),
                status_code=status_code,
                duration_ms=round((perf_counter() - started) * 1000),
                user_id=getattr(request.state, "activity_user_id", None),
                session_id=getattr(request.state, "activity_session_id", None),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                query_keys=sorted(set(request.query_params.keys())),
            )

# 라우터 등록
app.include_router(question_controller.router)
app.include_router(board_controller.router)
app.include_router(hokeytoon_controller.router)
app.include_router(menu_controller.router)
app.include_router(auth_controller.router)
app.include_router(admin_controller.router)
app.include_router(file_controller.router)
app.include_router(chat_controller.router)
app.include_router(inspection_controller.router)
app.include_router(analytics_controller.router)
app.include_router(analytics_insight_controller.router)

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
            <a href="/docs" class="btn">API 문서 바로가기</a>
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


