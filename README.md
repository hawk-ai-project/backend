# Hawk-AI Backend

Hawk-AI의 REST API 서버입니다. FastAPI와 SQLAlchemy를 기반으로 질문 CRUD, 메뉴 조회·등록 API, CCTV 객체 탐지 이력 저장을 위한 데이터 모델을 제공합니다.

## 기술 스택

- Python
- FastAPI / Uvicorn
- SQLAlchemy 2
- MySQL / PyMySQL
- Pydantic 2
- Alembic

## 주요 기능

- 질문 목록, 상세 조회, 등록, 수정, 삭제
- SQL 파일을 로드해 실행하는 메뉴 API
- CCTV 객체 탐지 이력(`detection_log`) 모델
- Swagger UI와 ReDoc 자동 API 문서
- 프런트엔드 연동을 위한 CORS 설정

## 프로젝트 구조

```text
backend/
├── domain/question/
│   └── question_router.py  # 질문 API 라우터
├── migrations/             # Alembic 마이그레이션
├── sql/
│   └── menu.sql            # 메뉴 관련 Raw SQL
├── crud.py                 # 데이터 CRUD 로직
├── database.py             # DB 엔진, 세션, SQL 실행 컨텍스트
├── main.py                 # FastAPI 앱과 메뉴 API
├── models.py               # SQLAlchemy 모델
├── schemas.py              # Pydantic 요청·응답 스키마
├── sql_loader.py           # .sql 파일 로더
├── alembic.ini             # Alembic 설정
└── requirements.txt        # Python 패키지 목록
```

## 시작하기

### 1. 사전 요구 사항

- Python 3.10 이상
- MySQL 8 이상
- 프로젝트에서 사용할 MySQL 데이터베이스

### 2. 가상 환경 생성 및 활성화

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
python -m pip install -r requirements.txt
```

### 4. 데이터베이스 설정

현재 애플리케이션의 MySQL 접속 주소는 `database.py`의 `SQLALCHEMY_DATABASE_URL`에 지정되어 있습니다.

```python
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://사용자:비밀번호@호스트:3306/데이터베이스"
```

실행 전에 로컬 환경에 맞게 값을 변경하고 대상 데이터베이스를 생성해야 합니다. 서버 시작 시 SQLAlchemy 모델에 정의된 `question`과 `detection_log` 테이블은 자동으로 생성됩니다.

> `.env`에는 `DATABASE_URL` 등의 항목이 있지만 현재 코드에서는 이를 읽지 않습니다. 또한 `alembic.ini`의 마이그레이션 DB URL은 SQLite로 별도 설정되어 있으므로, Alembic을 사용할 때는 애플리케이션 DB와 동일한 주소로 맞춰 주세요. 비밀번호 등 민감한 값은 저장소에 커밋하지 않는 것을 권장합니다.

메뉴 API를 사용하려면 `sql/menu.sql`에서 조회·등록하는 `menu` 테이블도 데이터베이스에 준비되어 있어야 합니다.

### 5. 서버 실행

`backend` 디렉터리에서 실행합니다.

```bash
uvicorn main:app --reload
```

기본 주소는 다음과 같습니다.

- 서버 상태 페이지: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## API

### 질문 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `GET` | `/api/question/list` | 질문 목록 조회 |
| `GET` | `/api/question/detail/{question_id}` | 질문 상세 조회 |
| `POST` | `/api/question/create` | 질문 등록 |
| `PUT` | `/api/question/update/{question_id}` | 질문 수정 |
| `DELETE` | `/api/question/delete/{question_id}` | 질문 삭제 |

질문 등록·수정 요청 본문:

```json
{
  "subject": "질문 제목",
  "content": "질문 내용"
}
```

### 메뉴 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `GET` | `/api/menu/list` | 활성 메뉴 목록 조회 |
| `GET` | `/api/menu/{menu_id}` | 메뉴 상세 조회 |
| `POST` | `/api/menu` | 메뉴 등록 |

메뉴 등록 요청 본문:

```json
{
  "name": "시스템 관리",
  "path": "/system",
  "icon": "settings",
  "is_use": 1,
  "sort_order": 5
}
```

## 데이터 모델

### `question`

- `id`: 질문 ID
- `subject`: 제목
- `content`: 내용
- `create_date`: 생성 일시

### `detection_log`

- `id`: 탐지 이력 ID
- `camera_id`: 카메라 ID
- `object_type`: 탐지 객체 종류
- `confidence`: AI 신뢰도
- `bbox_coordinates`: 바운딩 박스 좌표
- `image_path`: 캡처 이미지 경로
- `detected_at`: 탐지 일시

현재 `detection_log` 저장 로직은 `crud.py`에 구현되어 있지만 이를 노출하는 API 라우트는 아직 등록되어 있지 않습니다.

## Alembic 사용

먼저 `alembic.ini`의 `sqlalchemy.url`을 사용할 DB에 맞춘 뒤 아래 명령을 실행합니다.

```bash
alembic upgrade head
```

모델 변경 후 새 마이그레이션을 만들려면 다음 명령을 사용합니다.

```bash
alembic revision --autogenerate -m "변경 내용"
```

> 기존 첫 마이그레이션과 현재 SQLAlchemy 모델의 구성이 다를 수 있으므로, 운영 DB에 적용하기 전 생성되는 변경 사항을 반드시 검토하세요.
