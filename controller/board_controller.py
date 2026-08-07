from fastapi import APIRouter, Query

from domain.board import Board, BoardPage
from service import board_service


router = APIRouter(prefix="/api/boards", tags=["게시판"])


@router.get("", response_model=BoardPage)
def get_board_list(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    keyword: str | None = None,
):
    return board_service.get_board_list(page, pageSize, keyword)


@router.get("/{board_id}", response_model=Board)
def get_board_detail(board_id: int):
    return board_service.get_board_detail(board_id)
