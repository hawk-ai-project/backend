from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse

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
from domain.file import BoardImageUploadResponse
from service import board_service, file_service


router = APIRouter(prefix="/api/boards", tags=["게시판"])


@router.post("/images", response_model=BoardImageUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_board_image(file: UploadFile = File(...), auth=Depends(current_auth)):
    try:
        return file_service.upload_board_image(file, auth[0]["id"])
    finally:
        file.file.close()


@router.post("/images/from-inspection/{inspection_id}", response_model=BoardImageUploadResponse)
def copy_inspection_image(inspection_id: int, auth=Depends(current_auth)):
    return file_service.copy_inspection_image_to_board(inspection_id, auth[0])


@router.get("/images/{object_key:path}")
def read_board_image(object_key: str):
    stored_file, content_type = file_service.open_board_image(object_key)

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/authors/{user_id}/profile-image")
def read_board_author_profile_image(user_id: int):
    stored_file, content_type = file_service.open_public_profile_image(user_id)

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=300"},
    )


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
