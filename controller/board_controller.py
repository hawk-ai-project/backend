from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status

from controller.auth_controller import current_auth
from domain.board import (
    Board,
    BoardAIGenerateRequest,
    BoardAIJob,
    BoardAIJobAccepted,
    BoardCreate,
    BoardPage,
    BoardUpdate,
)
from service import board_service


router = APIRouter(prefix="/api/boards", tags=["게시판"])


@router.post(
    "/ai/generate",
    response_model=BoardAIJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_board_draft(
    payload: BoardAIGenerateRequest,
    background_tasks: BackgroundTasks,
    auth=Depends(current_auth),
):
    job = board_service.create_board_ai_job(payload, auth[0]["id"])
    background_tasks.add_task(board_service.run_board_ai_job, job["jobId"], payload)
    return job


@router.get("/ai/jobs", response_model=list[BoardAIJob])
def get_board_ai_jobs(auth=Depends(current_auth)):
    return board_service.list_board_ai_jobs(auth[0]["id"])


@router.get("/ai/generate/{job_id}", response_model=BoardAIJob)
def get_board_ai_job(job_id: str, auth=Depends(current_auth)):
    return board_service.get_board_ai_job(job_id, auth[0]["id"])


@router.patch("/ai/generate/{job_id}/read", response_model=BoardAIJob)
def read_board_ai_job(job_id: str, auth=Depends(current_auth)):
    return board_service.read_board_ai_job(job_id, auth[0]["id"])


@router.get("", response_model=BoardPage)
def get_board_list(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    keyword: str | None = None,
    category: str | None = None,
):
    return board_service.get_board_list(page, pageSize, keyword, category)


@router.get("/{board_id}", response_model=Board)
def get_board_detail(board_id: int):
    return board_service.get_board_detail(board_id)


@router.post("", response_model=Board, status_code=status.HTTP_201_CREATED)
def create_board(payload: BoardCreate, auth=Depends(current_auth)):
    return board_service.create_board(payload, auth[0])


@router.patch("/{board_id}", response_model=Board)
def update_board(board_id: int, payload: BoardUpdate, auth=Depends(current_auth)):
    return board_service.update_board(board_id, payload, auth[0])


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: int, auth=Depends(current_auth)):
    board_service.delete_board(board_id, auth[0])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
