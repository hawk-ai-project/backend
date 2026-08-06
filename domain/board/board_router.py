# domain/board/board_router.py

from fastapi import APIRouter, Query

from domain.board import board_service


router = APIRouter(
    prefix="/api/boards",
    tags=["게시판"],
)


@router.get("")
def get_board_list(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    keyword: str | None = None,
):
    return board_service.get_board_list(
        page=page,
        page_size=pageSize,
        keyword=keyword,
    )


@router.get("/{board_id}")
def get_board_detail(board_id: int):
    return board_service.get_board_detail(board_id)