# Hawk-AI Backend

FastAPI와 MySQL 기반의 REST API 서버입니다. ORM 모델과 세션을 사용하지 않고 `common/db.py`의 직접 SQL 실행 함수를 통해 데이터베이스에 접근합니다.

## 아키텍처

```text
backend/
├── common/
│   └── db.py                   # 연결 풀과 직접 SQL 실행 함수
├── domain/                     # 도메인 요청·응답 모델
│   ├── board.py
│   ├── menu.py
│   └── question.py
├── repository/                 # SQL 작성 및 DB 접근
│   ├── board_repository.py
│   ├── menu_repository.py
│   └── question_repository.py
├── service/                    # 비즈니스 로직
│   ├── board_service.py
│   ├── menu_service.py
│   └── question_service.py
├── controller/                 # FastAPI 라우터
│   ├── board_controller.py
│   ├── menu_controller.py
│   └── question_controller.py
├── sql/
│   └── schema.sql              # MySQL 스키마
├── config.py
├── main.py
└── requirements.txt
```

호출 방향은 다음과 같습니다.

```text
HTTP 요청 → controller → service → repository → common.db → MySQL
```

- `domain`: Pydantic 모델과 도메인 데이터 구조만 정의합니다.
- `repository`: SQL을 작성하고 `fetch_query`, `execute_query`를 호출합니다.
- `service`: 조회 결과 검증, 예외 처리, 페이지 계산 등 비즈니스 규칙을 처리합니다.
- `controller`: 요청 파라미터를 받고 service를 호출합니다.

## 데이터베이스 설정

`backend/.env`에 다음 값을 설정합니다.

```env
DATABASE_URL=mysql+pymysql://사용자:비밀번호@호스트:3306/데이터베이스
SECRET_KEY=충분히-긴-비밀키
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

ORM이 스키마를 자동 생성하지 않으므로 서버 실행 전에 `sql/schema.sql`을 직접 적용해야 합니다.

## Repository 작성 예

```python
from common.db import execute_query, fetch_query


def find_by_id(item_id: int):
    return fetch_query(
        "SELECT id, name FROM items WHERE id = %s",
        (item_id,),
        one=True,
    )


def create(name: str) -> int:
    return execute_query(
        "INSERT INTO items (name) VALUES (%s)",
        (name,),
    )
```

값은 SQL 문자열에 직접 결합하지 말고 반드시 `%s` 플레이스홀더와 인자 튜플로 전달합니다.

## 실행

```bash
python -m pip install -r requirements.txt
cd backend
uvicorn main:app --reload
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## MinIO file API

For an existing database, create the metadata table before starting the API:

```bash
mysql -u USER -p DATABASE_NAME < backend/sql/files.sql
```

New databases receive the same `files` table from `backend/sql/schema.sql`.

Copy the MinIO values from `.env.example` into `.env`. The backend access key
and secret must match `MINIO_APP_ACCESS_KEY` and `MINIO_APP_SECRET_KEY` in the
MinIO environment file.

Upload a file as authenticated `multipart/form-data`:

```bash
curl -X POST http://localhost:8000/api/files \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "file=@sample.jpg"
```

Send the same authorization header to the returned `downloadUrl` to download
the file. An object is isolated by user ID, so only its uploader can download
or delete it. The default limit is 20 MB and can be changed with
`MAX_UPLOAD_SIZE_MB`.
