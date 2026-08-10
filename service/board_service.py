import math

from fastapi import HTTPException

from domain.board import BoardCreate, BoardUpdate
from repository import board_repository


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
    return board


def _ensure_can_manage(board_id: int, user: dict) -> None:
    owner_id = board_repository.find_author_id(board_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if owner_id != user["id"] and user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="게시글을 변경할 권한이 없습니다.")


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
