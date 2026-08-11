import math
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from client import ai_client
from domain.board import BoardAIGenerateRequest, BoardCreate, BoardUpdate
from repository import board_repository
from service import board_draft_service


_ai_jobs: dict[str, dict] = {}
_ai_jobs_lock = Lock()


def get_board_list(
    page: int,
    page_size: int,
    keyword: str | None = None,
    category: str | None = None,
) -> dict:
    items, total = board_repository.find_all(page, page_size, keyword, category)
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "totalItems": total,
        "totalPages": math.ceil(total / page_size) if total else 0,
    }


def get_board_detail(board_id: int) -> dict:
    board = board_repository.find_by_id(board_id, increment_view=True)
    if board is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if any(key in board for key in ("title", "summary", "content")):
        clean = board_draft_service.sanitize_board_draft(
            board,
            location="점검 현장",
            waste_summary=board.get("summary") or "점검 결과를 확인해 주세요.",
        )
        board.update(clean)
    return board


def _ensure_can_manage(board_id: int, user: dict) -> None:
    owner_id = board_repository.find_author_id(board_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="작성자만 게시글을 변경할 수 있습니다.")


def create_board(payload: BoardCreate, user: dict) -> dict:
    try:
        board_id = board_repository.create(payload.model_dump(), user["id"])
    except board_repository.InvalidCategoryError:
        raise HTTPException(status_code=422, detail="사용할 수 없는 카테고리입니다.") from None
    board = board_repository.find_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=500, detail="생성된 게시글을 조회할 수 없습니다.")
    return board


def update_board(board_id: int, payload: BoardUpdate, user: dict) -> dict:
    _ensure_can_manage(board_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        board = board_repository.find_by_id(board_id)
        if board is None:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        return board
    try:
        board_repository.update(board_id, changes)
    except board_repository.InvalidCategoryError:
        raise HTTPException(status_code=422, detail="사용할 수 없는 카테고리입니다.") from None
    board = board_repository.find_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return board


def delete_board(board_id: int, user: dict) -> None:
    _ensure_can_manage(board_id, user)
    if not board_repository.soft_delete(board_id):
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")


def generate_board_draft(payload: BoardAIGenerateRequest) -> dict[str, str]:
    try:
        draft = ai_client.generate_board(payload.model_dump())
        # This job payload is copied into the editor later. Validate it again
        # here so a malformed model result cannot be persisted in the browser.
        return board_draft_service.sanitize_board_draft(
            draft,
            location=payload.location,
            waste_summary=payload.wasteSummary,
        )
    except ai_client.AIServerError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ImportError, RuntimeError, OSError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"AI 모델을 사용할 수 없습니다: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=f"AI 생성 결과를 처리할 수 없습니다: {error}",
        ) from error


def create_board_ai_job(payload: BoardAIGenerateRequest, user_id: int) -> dict:
    job_id = str(uuid4())
    job = {
        "jobId": job_id,
        "userId": user_id,
        "status": "PENDING",
        "isRead": False,
        "createdAt": datetime.now(timezone.utc),
        "completedAt": None,
        "title": None,
        "summary": None,
        "content": None,
        "error": None,
    }
    with _ai_jobs_lock:
        _ai_jobs[job_id] = job
    return {"jobId": job_id, "status": "PENDING"}


def run_board_ai_job(job_id: str, payload: BoardAIGenerateRequest) -> None:
    with _ai_jobs_lock:
        job = _ai_jobs.get(job_id)
        if job is None:
            return
        job["status"] = "RUNNING"

    try:
        result = generate_board_draft(payload)
        with _ai_jobs_lock:
            job = _ai_jobs.get(job_id)
            if job is not None:
                job.update(result)
                job["status"] = "COMPLETED"
                job["completedAt"] = datetime.now(timezone.utc)
    except HTTPException as error:
        with _ai_jobs_lock:
            job = _ai_jobs.get(job_id)
            if job is not None:
                job["status"] = "FAILED"
                job["error"] = str(error.detail)
                job["completedAt"] = datetime.now(timezone.utc)
    except Exception as error:
        with _ai_jobs_lock:
            job = _ai_jobs.get(job_id)
            if job is not None:
                job["status"] = "FAILED"
                job["error"] = f"AI 글 생성 중 오류가 발생했습니다: {error}"
                job["completedAt"] = datetime.now(timezone.utc)


def _public_ai_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key != "userId"}


def list_board_ai_jobs(user_id: int) -> list[dict]:
    with _ai_jobs_lock:
        jobs = [
            _public_ai_job(job.copy())
            for job in _ai_jobs.values()
            if job["userId"] == user_id
        ]
    return sorted(jobs, key=lambda job: job["createdAt"], reverse=True)


def get_board_ai_job(job_id: str, user_id: int) -> dict:
    with _ai_jobs_lock:
        job = _ai_jobs.get(job_id)
        if job is None or job["userId"] != user_id:
            raise HTTPException(status_code=404, detail="AI 생성 작업을 찾을 수 없습니다.")
        return _public_ai_job(job.copy())


def read_board_ai_job(job_id: str, user_id: int) -> dict:
    with _ai_jobs_lock:
        job = _ai_jobs.get(job_id)
        if job is None or job["userId"] != user_id:
            raise HTTPException(status_code=404, detail="AI 생성 작업을 찾을 수 없습니다.")
        job["isRead"] = True
        return _public_ai_job(job.copy())
